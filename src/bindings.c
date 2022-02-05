#include "bindings.h"

#include "debug.h"
#include "utils.h"

#define BMN_CALLBACK_ERROR_OFFSET (1 << 10)
#define BMN_UNKNOWN_ERROR         BMN_CALLBACK_ERROR_OFFSET
#define BMN_ATTRIBUTE_ERROR       BMN_CALLBACK_ERROR_OFFSET + 1
#define BMN_FILE_NOT_FOUND        BMN_CALLBACK_ERROR_OFFSET + 2
#define BMN_OS_ERROR              BMN_CALLBACK_ERROR_OFFSET + 3

#define EMIT_WRAPPER_WARNING_FMT(...) \
    PyErr_WarnFormat(pysqlite_WrapperWarning, 0, __VA_ARGS__)
#define EMIT_RESULT_IGNORED_WARNING(METH) \
    EMIT_WRAPPER_WARNING_FMT("Result of calling '%s' is ignored", (METH))
#define RAISE_NONE_RETURNED(OBJ, METH) \
    saveLocation((OBJ), (METH)); \
    RAISE_TYPE_ERROR((OBJ), "Method '%s' returned None", (METH))
#define RAISE_WRONG_RETURN_TYPE(OBJ, METH) \
    saveLocation((OBJ), (METH)); \
    RAISE_TYPE_ERROR((OBJ), "Unexpected return type from '%s' method ", (METH))
#define RAISE_NO_MANDATORY_METHOD(OBJ, METH) \
    saveLocation((OBJ), (METH)); \
    RAISE_NAME_ERROR((OBJ), "No mandatory method '%s' found", (METH))
#define CHECK_OUT_OF_RANGE(N, METH) \
    if((N) < 0 || (N) > INT_MAX) \
    { \
        RAISE_OVERFLOW_ERROR( \
                pObject, \
                "Method '%s' returned out of range number", \
                (METH)); \
        rc = BMN_CB_RESULT_UNEXPECTED_RETURNS; \
    } \
    else \
    { \
        rc = (int)(N); \
    }

extern PyObject* pysqlite_DatabaseError;
extern PyObject* pysqlite_OperationalError;
extern PyObject* pysqlite_WrapperError;
extern PyObject* pysqlite_WrapperWarning;
static int tracePyException(
        PyObject* object,
        const char* zMethodName,
        const char** pErrorString);

#ifdef NDEBUG
#    define BMN_CATCH_PY_EXCEPTION(OBJ, ATTR) \
        tracePyException((OBJ), (ATTR), NULL)
#else
static int testPyExceptionDebug(
        PyObject* object,
        const char* zAttribute,
        const char* zFile,
        const char* zFunction,
        int nLine)
{
    int err;
    const char* zError;
    err    = 0;
    zError = NULL;
    err    = tracePyException(object, zAttribute, &zError);
    if(zError)
    {
        bmnPrintf(zFile, nLine, zFunction, 1, "PY Exception: %s", zError);
    }
    return err;
}
#    define BMN_CATCH_PY_EXCEPTION(OBJ, ATTR) \
        testPyExceptionDebug( \
                (OBJ), \
                (ATTR), \
                __FILE__, \
                __FUNCTION_NAME__, \
                __LINE__)
#endif

static int tracePyException(
        PyObject* pObject,
        const char* zMethodName,
        const char** pErrorString)
{
    int rc;
    PyObject* pExcType;
    PyObject* pExcValue;
    PyObject* pExcTraceback;
    PyObject* pExcValueStr;
    PyObject* pExcStrValue;
    const char* zExcStrValue;

    BMN_ASSERT(PyErr_Occurred());
    rc = 0;
    PyErr_Fetch(&pExcType, &pExcValue, &pExcTraceback);
    PyErr_NormalizeException(&pExcType, &pExcValue, &pExcTraceback);
    pExcStrValue = PyObject_Repr(pExcValue);
    pExcValueStr = PyUnicode_AsEncodedString(pExcStrValue, "utf-8", "Error ~");
    zExcStrValue = PyBytes_AS_STRING(pExcValueStr);
    BMN_VERBOSE("ex:%s location:%s", zExcStrValue, zMethodName);

    saveLocation(pObject, zMethodName);

    if(PyExc_AttributeError == pExcType && zMethodName &&
       strstr(zExcStrValue, zMethodName))
    {
        rc = BMN_ATTRIBUTE_ERROR;
    }
    else if(PyExc_NotImplementedError == pExcType)
    {
        rc = BMN_ATTRIBUTE_ERROR;
        BMN_VERBOSE("Method %s raised NotImplemetedError", zMethodName);
    }
    else if(PyExc_FileNotFoundError == pExcType && zMethodName &&
            !strcmp(zMethodName, "open"))
    {
        rc = BMN_FILE_NOT_FOUND;
    }
    else if(pExcType == PyExc_OSError && zMethodName &&
            !strcmp(zMethodName, "open"))
    {
        rc = BMN_OS_ERROR;
    }
    else
    {
        rc = BMN_UNKNOWN_ERROR;
        PyErr_Restore(pExcType, pExcValue, pExcTraceback);
        PyErr_WriteUnraisable(pObject);
#if PY_VERSION_HEX >= 0x03080000
        BMN_TRACE("unraisable exception  %s", zExcStrValue);
#endif
        goto skip;
    }
    if(BMN_ATTRIBUTE_ERROR == rc)
    {
        BMN_VERBOSE("No method '%s'", zMethodName);
    }
    else if(pErrorString)
    {
        *pErrorString = zExcStrValue;
    }
    else
    {
        BMN_ERROR("Exception: %s", zExcStrValue);
    }
    Py_XDECREF(pExcType);
    Py_XDECREF(pExcValue);
    Py_XDECREF(pExcTraceback);
skip:
    Py_XDECREF(pExcStrValue);
    Py_XDECREF(pExcValueStr);
    BMN_ASSERT(rc);
    return rc;
}
static int parseResultCode(PyObject* pResult, int* rc)
{
    if(Py_None == pResult)
    {
        *rc = SQLITE_OK;
    }
    else if(PyLong_Check(pResult))
    {
        *rc = PyLong_AsLong(pResult);
        /*
    TODO:
    -1 can be confusing, but calling PyErr_Occurred required keeping GIL
whereas we have plans to avoid it
*/
#if 0
            if( -1 == rc && PyErr_Occurred() ){
                BMN_ASSERT(0);
            }
#endif
    }
    else
    {
        *rc = BMN_CB_RESULT_UNEXPECTED_RETURNS;
        return 1;
    }
    return 0;
}

static int checkFileHandlerObject(PyObject* pHost, PyObject* pObject)
{
    BMN_ASSERT(pHost);
    BMN_ASSERT(pObject);
    if(Py_None == pObject)
    {
        RAISE_NONE_RETURNED(pHost, "open");
        return 1;
    }
    if(PyLong_Check(pObject) || PyFloat_Check(pObject) || PyBool_Check(pObject))
    {
        RAISE_WRONG_RETURN_TYPE(pHost, "open");
        return 1;
    }
    return 0;
}

extern int callOpenMethod(
        PyObject* pObject,
        BmnvfsFile* pFile,
        const char* zFilename,
        int flags,
        int* pOutFlags)
{
    BMN_TRACE_MARK;
    int rc;
    PyGILState_STATE gilstate;
    PyObject* pResult;
    _Py_IDENTIFIER(open);

    rc = SQLITE_OK;
    BMN_ASSERT(pFile);
    pFile->pBuffer = NULL;
    gilstate       = PyGILState_Ensure();
    pResult =
            _PyObject_CallMethodId(pObject, &PyId_open, "sI", zFilename, flags);

    if(pResult)
    {
        // no callback errors
        if(0 == checkFileHandlerObject(pObject, pResult))
        {
            // valid handler (almost) - ok
            rc                  = SQLITE_OK;
            pFile->pFileWrapper = pResult;
            if(pOutFlags)
            {
                *pOutFlags = flags;
            }
        }
        else if(PyTuple_CheckExact(pResult))
        {
            // tuple - ok
            if(2 != PyTuple_GET_SIZE(pResult))
            {
                // valid size - ok
                // borrowed !
                PyObject* pFirst  = PyTuple_GET_ITEM(pResult, 0);
                PyObject* pSecond = PyTuple_GET_ITEM(pResult, 1);
                if(0 == checkFileHandlerObject(pObject, pFirst))
                {
                    // both are valid - ok
                    rc                  = SQLITE_OK;
                    pFile->pFileWrapper = pFirst;
                    if(pOutFlags)
                    {
                        *pOutFlags = PyLong_AsLong(pSecond);
                    }
                }
                else if(!PyLong_Check(pSecond))
                {
                    // second is wrong result
                    rc = BMN_CB_RESULT_UNEXPECTED_RETURNS;
                }
                else
                {
                    // first is wrong  result
                    rc = BMN_CB_RESULT_UNEXPECTED_RETURNS;
                }
            }
            else
            {
                // bad tuple size
                RAISE_WRONG_RETURN_TYPE(pObject, "open");
                rc = BMN_CB_RESULT_UNEXPECTED_RETURNS;
            }
        }
        else
        {
            // wrong result
            rc = BMN_CB_RESULT_UNEXPECTED_RETURNS;
        }
    }
    else
    {
        // callback errors
        int ec;
        ec = BMN_CATCH_PY_EXCEPTION(pObject, "open");
        if(BMN_ATTRIBUTE_ERROR == ec)
        {
            rc = BMN_CB_RESULT_NO_HANDLER;
        }
        else if(BMN_FILE_NOT_FOUND == ec)
        {
            rc = SQLITE_CANTOPEN;
        }
        else if(BMN_OS_ERROR == ec)
        {
            // TODO: may be ther's more appropriate error
            rc = SQLITE_CANTOPEN;
        }
        else
        {
            rc = BMN_CB_RESULT_HANDLER_LOGIC_ERROR;
        }
    }

    BMN_TRACE_ERROR(rc);
    if(rc)
    {
        Py_XDECREF(pResult);
        pResult             = NULL;
        pFile->pFileWrapper = NULL;
    }
    PyGILState_Release(gilstate);
    BMN_ASSERT(rc ^ (NULL != pFile->pFileWrapper));

    BMN_VERBOSE(
            "input: %s flags: %d out flags: %d",
            zFilename,
            flags,
            pOutFlags ? *pOutFlags : -1);
    return rc;
}

extern int callCloseMethod(PyObject* pObject, BmnvfsFile* pFile)
{
    BMN_TRACE_MARK;
    int rc;
    PyGILState_STATE gilstate;
    PyObject* pResult;
    _Py_IDENTIFIER(close);

    rc = SQLITE_OK;
    BMN_ASSERT(pFile);
    BMN_ASSERT(pFile->pFileWrapper);
    gilstate = PyGILState_Ensure();
    pResult  = _PyObject_CallMethodId(
            pObject,
            &PyId_close,
            "O",
            pFile->pFileWrapper);
    if(pResult)
    {
        if(Py_None != pResult)
        {
            EMIT_RESULT_IGNORED_WARNING("close");
        }
        Py_DECREF(pResult);
        pResult = NULL;
    }
    else
    {
        int ec;

        ec = BMN_CATCH_PY_EXCEPTION(pObject, "close");
        if(BMN_ATTRIBUTE_ERROR == ec)
        {
            RAISE_NO_MANDATORY_METHOD(pObject, "close");
            rc = BMN_CB_RESULT_NO_HANDLER;
        }
        else if(ec)
        {
            rc = BMN_CB_RESULT_HANDLER_LOGIC_ERROR;
        }
    }
    pFile->pFileWrapper = NULL;
    BMN_MEM_FREE(pFile->pBuffer);
    pFile->pBuffer = NULL;
    PyGILState_Release(gilstate);
    return rc;
}

extern int callFullPathname(
        PyObject* pObject,
        const char* zFilename,
        int nOut,
        char* zOut)
{
    BMN_TRACE_MARK;
    int rc;
    PyGILState_STATE gilstate;
    PyObject* pResult;
    Py_ssize_t nLength;

    _Py_IDENTIFIER(full_pathname);
    rc       = SQLITE_OK;
    gilstate = PyGILState_Ensure();

    BMN_VERBOSE("input: %s out: %d", zFilename, nOut);
    pResult = _PyObject_CallMethodId(
            pObject,
            &PyId_full_pathname,
            "s I",
            zFilename,
            nOut);
    BMN_VERBOSE_P(pResult);
    if(pResult)
    {
        // no callback errors - ok
        const char* zBuffer;
        if(PyUnicode_Check(pResult))
        {
            // string - ok
            zBuffer = PyUnicode_AsUTF8AndSize(pResult, &nLength);
            if(zBuffer)
            {
                // utf8 - ok
                if(nLength <= nOut)
                {
                    // length is valid - ok
                    memcpy(zOut, zBuffer, nLength + 1);
                    rc = SQLITE_OK;
                }
                else
                {
                    // overflow - fail

                    /*
                    SQLite will always allocate at least mxPathname+1 bytes for
                    the output buffer xFullPathname. The exact size of the
                    output buffer is also passed as a parameter to both methods.
                    If the output buffer is not large enough, SQLITE_CANTOPEN
                    should be returned. Since this is handled as a fatal error
                    by SQLite, vfs implementations should endeavor to prevent
                    this by setting mxPathname to a sufficiently large value.
                    */
                    RAISE_OVERFLOW_ERROR(
                            pObject,
                            "String returned by method 'full_pathname' longer than expected.");
                    rc = SQLITE_CANTOPEN;
                }
            }
            else
            {
                // utf8 - fail
                BMN_ERROR(
                        "Impossible convert result of method 'full_pathname' to utf8.");
                rc = BMN_CB_RESULT_UNEXPECTED_RETURNS;
            }
        }
        else if(Py_None == pResult)
        {
            // none is possible - ok
            BMN_VERBOSE("'full_pathname' returned None");
            rc = BMN_CB_RESULT_NO_HANDLER;
        }
        else
        {
            // result type - fail
            RAISE_WRONG_RETURN_TYPE(pObject, "full_pathname");
            rc = BMN_CB_RESULT_UNEXPECTED_RETURNS;
        }
        Py_DECREF(pResult);
        pResult = NULL;
    }
    else
    {
        int ec;
        ec = BMN_CATCH_PY_EXCEPTION(pObject, "full_pathname");
        if(BMN_ATTRIBUTE_ERROR == ec)
        {
            rc = BMN_CB_RESULT_NO_HANDLER;
        }
        else if(ec)
        {
            rc = BMN_CB_RESULT_HANDLER_LOGIC_ERROR;
        }
    }
    PyGILState_Release(gilstate);
    BMN_VERBOSE_ERROR(rc);
    return rc;
}

extern int callAccessMethod(
        PyObject* pObject,
        const char* zPath,
        int flags,
        int* pResOut)
{
    BMN_TRACE_MARK;
    int rc;
    PyObject* pResult;
    PyGILState_STATE gilstate;
    _Py_IDENTIFIER(access);

    BMN_ASSERT(
            flags == SQLITE_ACCESS_EXISTS || flags == SQLITE_ACCESS_READ ||
            flags == SQLITE_ACCESS_READWRITE);

    rc       = SQLITE_OK;
    gilstate = PyGILState_Ensure();
    pResult =
            _PyObject_CallMethodId(pObject, &PyId_access, "s I", zPath, flags);
    if(pResult)
    {
        if(Py_None == pResult)
        {
            *pResOut = 0;
            rc       = BMN_CB_RESULT_NO_HANDLER;
        }
        else if(PyBool_Check(pResult))
        {
            if(Py_True == pResult)
            {
                *pResOut = 1;
            }
            else
            {
                *pResOut = 0;
            }
        }
        else
        {
            RAISE_WRONG_RETURN_TYPE(pObject, "access");
            rc = BMN_CB_RESULT_UNEXPECTED_RETURNS;
        }
        Py_DECREF(pResult);
        pResult = NULL;
    }
    else
    {
        int ec;
        ec = BMN_CATCH_PY_EXCEPTION(pObject, "access");
        if(BMN_ATTRIBUTE_ERROR == ec)
        {
            rc = BMN_CB_RESULT_NO_HANDLER;
        }
        else if(ec)
        {
            rc = BMN_CB_RESULT_HANDLER_LOGIC_ERROR;
        }
    }
    BMN_VERBOSE_ERROR(rc);
    PyGILState_Release(gilstate);
    return rc;
}

extern int callDeleteMethod(PyObject* pObject, const char* zPath, int syncDir)
{
    BMN_TRACE_MARK;

    PyGILState_STATE gilstate;
    PyObject* pResult;
    int rc;
    _Py_IDENTIFIER(delete);

    rc       = SQLITE_OK;
    gilstate = PyGILState_Ensure();
    BMN_VERBOSE_IO("file to delete:%s", zPath);
    pResult = _PyObject_CallMethodId(
            pObject,
            &PyId_delete,
            "s I",
            zPath,
            syncDir);
    if(pResult)
    {
        if(Py_None != pResult)
        {
            EMIT_RESULT_IGNORED_WARNING("delete");
        }
        Py_DECREF(pResult);
        pResult = NULL;
        rc      = SQLITE_OK;
    }
    else
    {
        int ec;
        ec = BMN_CATCH_PY_EXCEPTION(pObject, "delete");
        if(BMN_ATTRIBUTE_ERROR == ec)
        {
            rc = BMN_CB_RESULT_NO_HANDLER;
        }
        else if(ec)
        {
            rc = BMN_CB_RESULT_HANDLER_LOGIC_ERROR;
        }
    }
    PyGILState_Release(gilstate);
    return rc;
}

int callReadMethod(
        BmnvfsInfo* vfsInfo,
        BmnvfsFile* vfsFile,
        char* buffer,
        Py_ssize_t amount,
        sqlite_int64 offset)
{
    int rc;
    PyGILState_STATE gilState = PyGILState_Ensure();

    PyObject* result = PyObject_CallMethod(
            vfsInfo->pWrapper,
            "read",
            "OIL",
            vfsFile->pFileWrapper,
            amount,
            offset);
    if(result == NULL)
    {
        rc = BMN_CATCH_PY_EXCEPTION(vfsInfo->pWrapper, "read");
        PyGILState_Release(gilState);
        if(rc != BMN_ATTRIBUTE_ERROR)
        {
            return BMN_CB_RESULT_HANDLER_LOGIC_ERROR;
        }
        return BMN_CB_RESULT_NO_HANDLER;
    }

    if(result == Py_None)
    {
        memset(buffer, '\0', amount);
        rc = SQLITE_IOERR_SHORT_READ;
    }
    else if(PyBytes_Check(result))
    {
        Py_ssize_t resultLength = PyBytes_Size(result);
        if(resultLength == amount)
        {
            memcpy(buffer, PyBytes_AsString(result), resultLength);
            rc = SQLITE_OK;
        }
        else if(resultLength < amount)
        {
            memcpy(buffer, PyBytes_AsString(result), resultLength);
            memset(buffer + resultLength, '\0', amount - resultLength);
            rc = SQLITE_IOERR_SHORT_READ;
        }
        else
        {
            BMN_ERROR("Bad read result size: %d", resultLength);
            RAISE_VALUE_ERROR(
                    vfsInfo->pWrapper,
                    "read",
                    "Method 'read' returned wrong number of bytes");
            rc = BMN_CB_RESULT_UNEXPECTED_RETURNS;
        }
    }
    else
    {
        RAISE_WRONG_RETURN_TYPE(vfsInfo->pWrapper, "read")
        rc = BMN_CB_RESULT_UNEXPECTED_RETURNS;
    }

    Py_DECREF(result);
    PyGILState_Release(gilState);
    return rc;
}

int callWriteMethod(
        PyObject* object,
        BmnvfsFile* vfsFile,
        const char* buffer,
        Py_ssize_t amount,
        sqlite_int64 offset)
{
    int rc;
    PyGILState_STATE gilState = PyGILState_Ensure();

    PyObject* result = PyObject_CallMethod(
            object,
            "write",
            "Oy#L",
            vfsFile->pFileWrapper,
            buffer,
            amount,
            offset);
    if(result)
    {
        Py_DECREF(result);
        rc = SQLITE_OK;
    }
    else
    {
        BMN_CATCH_PY_EXCEPTION(object, "write");
        rc = BMN_CB_RESULT_HANDLER_LOGIC_ERROR;
    }
    PyGILState_Release(gilState);
    return rc;
}

extern int callDeviceCharacteristicsMethod(PyObject* pObject, BmnvfsFile* pFile)
{
    BMN_TRACE_MARK;
    BMN_ASSERT(pFile->pFileWrapper);
    int rc;
    PyGILState_STATE gilstate;
    PyObject* pResult;
    _Py_IDENTIFIER(device_characteristics);

    rc       = SQLITE_DEFAULT_DEVICE_CHARACTERISTICS;
    gilstate = PyGILState_Ensure();
    pResult  = _PyObject_CallMethodId(
            pObject,
            &PyId_device_characteristics,
            "O",
            pFile->pFileWrapper);
    if(pResult)
    {
        if(PyLong_Check(pResult))
        {
            rc = PyLong_AsLong(pResult);
            if(rc < 0 || rc > INT_MAX)
            {
                RAISE_OVERFLOW_ERROR(
                        pObject,
                        "Method 'device_characteristics' returned out of range number");
                rc = BMN_CB_RESULT_UNEXPECTED_RETURNS;
            }
        }
        else if(Py_None == pResult)
        {
            rc = BMN_CB_RESULT_NO_HANDLER;
        }
        else
        {
            RAISE_WRONG_RETURN_TYPE(pObject, "device_characteristics");
            rc = BMN_CB_RESULT_UNEXPECTED_RETURNS;
        }
        Py_DECREF(pResult);
        pResult = NULL;
    }
    else
    {
        int ec;
        ec = BMN_CATCH_PY_EXCEPTION(pObject, "device_characteristics");
        if(BMN_ATTRIBUTE_ERROR == ec)
        {
            rc = BMN_CB_RESULT_NO_HANDLER;
        }
        else if(ec)
        {
            rc = BMN_CB_RESULT_HANDLER_LOGIC_ERROR;
        }
    }
    PyGILState_Release(gilstate);
    return rc;
}

extern int callFileTruncateMethod(
        PyObject* pObject,
        BmnvfsFile* pFile,
        sqlite3_int64 iSize)
{
    BMN_TRACE_MARK;

    PyGILState_STATE gilstate;
    PyObject* pResult;
    int rc;
    _Py_IDENTIFIER(truncate);

    gilstate = PyGILState_Ensure();
    rc       = SQLITE_OK;
#if BMN_DEBUG_FILENAME_CONTROL
    BMN_VERBOSE_IO("truncate %s to %d", pFile->zFName, iSize);
#endif
    pResult = _PyObject_CallMethodId(
            pObject,
            &PyId_truncate,
            "O L",
            pFile->pFileWrapper,
            iSize);
    if(pResult)
    {
        if(Py_None != pResult)
        {
            EMIT_RESULT_IGNORED_WARNING("truncate");
        }
        Py_DECREF(pResult);
        pResult = NULL;
    }
    else
    {
        int ec;
        ec = BMN_CATCH_PY_EXCEPTION(pObject, "truncate");
        if(BMN_ATTRIBUTE_ERROR == ec)
        {
            rc = BMN_CB_RESULT_NO_HANDLER;
        }
        else if(ec)
        {
            rc = BMN_CB_RESULT_HANDLER_LOGIC_ERROR;
        }
    }
    PyGILState_Release(gilstate);
    BMN_TRACE_ERROR(rc);
    return rc;
}

extern int callFileSizeMethod(
        PyObject* pObject,
        BmnvfsFile* pFile,
        sqlite3_int64* pSize)
{
    BMN_TRACE_MARK;

    int rc;
    PyGILState_STATE gilstate;
    PyObject* pResult;
    _Py_IDENTIFIER(file_size);

    rc       = SQLITE_OK;
    gilstate = PyGILState_Ensure();
    pResult  = _PyObject_CallMethodId(
            pObject,
            &PyId_file_size,
            "O",
            pFile->pFileWrapper);
    if(pResult)
    {
        if(PyLong_Check(pResult))
        {
            *pSize = PyLong_AsLongLong(pResult);
            rc     = SQLITE_OK;
        }
        else if(Py_None == pResult)
        {
            RAISE_NO_MANDATORY_METHOD(pObject, "file_size");
            rc = BMN_CB_RESULT_NO_HANDLER;
        }
        else
        {
            RAISE_WRONG_RETURN_TYPE(pObject, "file_size");
            rc = BMN_CB_RESULT_UNEXPECTED_RETURNS;
        }
        Py_DECREF(pResult);
        pResult = NULL;
    }
    else
    {
        int ec;
        ec = BMN_CATCH_PY_EXCEPTION(pObject, "file_size");
        if(BMN_ATTRIBUTE_ERROR == ec)
        {
            rc = BMN_CB_RESULT_NO_HANDLER;
        }
        else if(ec)
        {
            rc = BMN_CB_RESULT_HANDLER_LOGIC_ERROR;
        }
    }
    PyGILState_Release(gilstate);
    BMN_VERBOSE_IO("File size %lld", *pSize);
    BMN_VERBOSE_ERROR(rc);
    return rc;
}

extern int callSyncMethod(PyObject* pObject, BmnvfsFile* pFile, int flags)
{
    BMN_TRACE_MARK;

    int rc;
    PyGILState_STATE gilstate;
    PyObject* pResult;
    _Py_IDENTIFIER(sync);

    rc = SQLITE_OK;
    BMN_ASSERT(pFile->pFileWrapper);
    gilstate = PyGILState_Ensure();
    pResult  = _PyObject_CallMethodId(
            pObject,
            &PyId_sync,
            "O I",
            pFile->pFileWrapper,
            flags);
    if(pResult)
    {
        if(Py_None != pResult)
        {
            EMIT_RESULT_IGNORED_WARNING("sync");
        }
        Py_DECREF(pResult);
        pResult = NULL;
        rc      = SQLITE_OK;
    }
    else
    {
        int ec;
        ec = BMN_CATCH_PY_EXCEPTION(pObject, "sync");
        if(BMN_ATTRIBUTE_ERROR == ec)
        {
            rc = BMN_CB_RESULT_NO_HANDLER;
        }
        else if(ec)
        {
            rc = BMN_CB_RESULT_HANDLER_LOGIC_ERROR;
        }
    }
    PyGILState_Release(gilstate);
    return rc;
}

extern int callSectorSizeMethod(PyObject* pObject, BmnvfsFile* pFile)
{
    BMN_TRACE_MARK;

    int rc;
    PyGILState_STATE gilstate;
    PyObject* pResult;
    _Py_IDENTIFIER(sector_size);

    rc       = SQLITE_OK;
    gilstate = PyGILState_Ensure();
    pResult  = _PyObject_CallMethodId(
            pObject,
            &PyId_sector_size,
            "O",
            pFile->pFileWrapper);
    if(pResult)
    {
        if(PyLong_Check(pResult))
        {
            long nSectorSize;
            nSectorSize = PyLong_AsLong(pResult);
            CHECK_OUT_OF_RANGE(nSectorSize, "sector_size");
        }
        else if(PyFloat_Check(pResult))
        {
            double fSectorSize;
            fSectorSize = PyFloat_AS_DOUBLE(pResult);
            CHECK_OUT_OF_RANGE(fSectorSize, "sector_size");
        }
        else if(Py_None == pResult)
        {
            // don't raise anything cause it is normal and comfortable behavior
            // for
            rc = BMN_CB_RESULT_NO_HANDLER;
        }
        else
        {
            RAISE_WRONG_RETURN_TYPE(pObject, "sector_size");
            rc = BMN_CB_RESULT_UNEXPECTED_RETURNS;
        }
        Py_DECREF(pResult);
        pResult = NULL;
    }
    else
    {
        int ec;
        ec = BMN_CATCH_PY_EXCEPTION(pObject, "sector_size");
        if(BMN_ATTRIBUTE_ERROR == ec)
        {
            rc = BMN_CB_RESULT_NO_HANDLER;
        }
        else if(ec)
        {
            rc = BMN_CB_RESULT_HANDLER_LOGIC_ERROR;
        }
    }
    BMN_VERBOSE_ERROR(rc);
    PyGILState_Release(gilstate);
    return rc;
}

extern int callRandomnessMethod(PyObject* pObject, int nByte, char* zByte)
{
    BMN_TRACE_MARK;

    int rc;
    PyGILState_STATE gilstate;
    PyObject* pResult;
    Py_ssize_t iResultLen;
    _Py_IDENTIFIER(random);

    rc       = BMN_CB_RESULT_NO_HANDLER;
    gilstate = PyGILState_Ensure();
    pResult  = _PyObject_CallMethodId(pObject, &PyId_random, "I", nByte);
    if(pResult)
    {
        if(Py_None == pResult)
        {
            BMN_VERBOSE("'random' returned None");
            rc = BMN_CB_RESULT_NO_HANDLER;
        }
        else if(PyBytes_Check(pResult))
        {
            iResultLen = PyBytes_GET_SIZE(pResult);
            BMN_VERBOSE_INT(iResultLen);
            if(nByte == iResultLen)
            {
                memcpy(zByte, PyBytes_AS_STRING(pResult), nByte);
                rc = nByte;
            }
            else
            {
                BMN_ERROR("Bad random result size:%d", iResultLen);
                RAISE_VALUE_ERROR(
                        pObject,
                        "random",
                        "Unexpected bytes length returned from 'random' method");
                rc = BMN_CB_RESULT_UNEXPECTED_RETURNS;
            }
        }
        else
        {
            RAISE_WRONG_RETURN_TYPE(pObject, "random");
            rc = BMN_CB_RESULT_UNEXPECTED_RETURNS;
        }
        Py_DECREF(pResult);
        pResult = NULL;
    }
    else
    {
        int ec;
        ec = BMN_CATCH_PY_EXCEPTION(pObject, "random");
        if(BMN_ATTRIBUTE_ERROR == ec)
        {
            rc = BMN_CB_RESULT_NO_HANDLER;
        }
        else if(ec)
        {
            rc = BMN_CB_RESULT_HANDLER_LOGIC_ERROR;
        }
    }
    PyGILState_Release(gilstate);
    return rc;
}

extern int callFileControlMethod(
        PyObject* pObject,
        BmnvfsFile* pFile,
        int iOperation,
        void* pArg)
{
    /*
  we're not going to call python for a while
  but we need to process this stuff anyway
  */
    int rc;
    PyGILState_STATE gilstate;
    PyObject* pResult;
    _Py_IDENTIFIER(file_control);

    rc = SQLITE_NOTFOUND;
    switch(iOperation)
    {
    case SQLITE_FCNTL_SIZE_HINT:
        /* 5
The SQLITE_FCNTL_SIZE_HINT opcode is used by SQLite to give the VFS layer a
hint of how large the database file will grow to be during the current
transaction. This hint is not guaranteed to be accurate but it is often close.
The underlying VFS might choose to preallocate database file space based on
this hint in order to help writes to the database file run faster.
*/
        BMN_VERBOSE_IO(
                "FILE CONTROL=> file size hint: %lld",
                *(sqlite3_int64*)pArg);
        break;
    case SQLITE_FCNTL_OVERWRITE:
        /* 11
The SQLITE_FCNTL_OVERWRITE opcode is invoked by SQLite after opening a write
transaction to indicate that, unless it is rolled back for some reason, the
entire database file will be overwritten by the current transaction. This is
used by VACUUM operations.
*/
        BMN_VERBOSE_IO(
                "FILE CONTROL=> vacuum file overrite: %lld",
                *(sqlite3_int64*)pArg);

        // rc = BMN_CALLBACK_ERROR;
        gilstate = PyGILState_Ensure();
        pResult  = _PyObject_CallMethodId(
                pObject,
                &PyId_file_control,
                "OIL",
                pFile->pFileWrapper,
                iOperation,
                *(sqlite3_int64*)pArg);
        if(pResult)
        {
            if(Py_None == pResult)
            {
                BMN_VERBOSE("'file_control' returned None");
                rc = BMN_CB_RESULT_NO_HANDLER;
            }
            else if(PyBool_Check(pResult))
            {
                if(Py_True == pResult)
                {
                    rc = BMN_CALLBACK_ERROR;
                    EMIT_WRAPPER_WARNING_FMT(
                            "VACUUM operation was refused by %s",
                            getObjectTypename(pObject));
                }
            }
            else
            {
                RAISE_WRONG_RETURN_TYPE(pObject, "file_control");
                rc = BMN_CB_RESULT_UNEXPECTED_RETURNS;
            }
            Py_DECREF(pResult);
            pResult = NULL;
        }
        else
        {
            int ec;
            ec = BMN_CATCH_PY_EXCEPTION(pObject, "file_control");
            if(BMN_ATTRIBUTE_ERROR == ec)
            {
                rc = BMN_CB_RESULT_NO_HANDLER;
            }
            else if(ec)
            {
                rc = BMN_CB_RESULT_HANDLER_LOGIC_ERROR;
            }
        }
        PyGILState_Release(gilstate);
        break;
    case SQLITE_FCNTL_BUSYHANDLER:
        /* 15
  The SQLITE_FCNTL_BUSYHANDLER file-control may be invoked by SQLite on the
  database file handle shortly after it is opened in order to provide a
  custom VFS with access to the connection's busy-handler callback. The
  argument is of type (void**) - an array of two (void *) values. The first
  (void *) actually points to a function of type (int (*)(void *)). In order
  to invoke the connection's busy-handler, this function should be invoked
  with the second (void *) in the array as the only argument. If it returns
  non-zero, then the operation should be retried. If it returns zero, the
  custom VFS should abandon the current operation.
  */
        BMN_VERBOSE_IO("FILE CONTROL=> busy handler ");
        break;
    case SQLITE_FCNTL_MMAP_SIZE:
        /* 18
  The SQLITE_FCNTL_MMAP_SIZE file control is used to query or set the
  maximum number of bytes that will be used for memory-mapped I/O. The
  argument is a pointer to a value of type sqlite3_int64 that is an advisory
  maximum number of bytes in the file to memory map. The pointer is
  overwritten with the old value. The limit is not changed if the value
  originally pointed to is negative, and so the current limit can be queried
  by passing in a pointer to a negative number. This file-control is used
  internally to implement PRAGMA mmap_size.
  */
        BMN_VERBOSE_IO("FILE CONTROL=> mmap size: %lld", *(sqlite3_int64*)pArg);
        break;
    case SQLITE_FCNTL_HAS_MOVED:
        /* 20
  The SQLITE_FCNTL_HAS_MOVED file control interprets its argument as a
  pointer to an integer and it writes a boolean into that integer depending
  on whether or not the file has been renamed, moved, or deleted since it
  was first opened.
  */
        BMN_VERBOSE_IO(
                "FILE CONTROL=> file moved: %s",
                0 == *(int*)pArg ? "TRUE" : "FALSE");
        break;
    case SQLITE_FCNTL_SYNC:
        /* 21
The SQLITE_FCNTL_SYNC opcode is generated internally by SQLite and sent to the
VFS immediately before the xSync method is invoked on a database file
descriptor. Or, if the xSync method is not invoked because the user has
configured SQLite with PRAGMA synchronous=OFF it is invoked in place of the
xSync method. In most cases, the pointer argument passed with this
file-control is NULL. However, if the database file is being synced as part of
a multi-database commit, the argument points to a nul-terminated string
containing the transactions super-journal file name. VFSes that do not need
this signal should silently ignore this opcode. Applications should not call
sqlite3_file_control() with this opcode as doing so may disrupt the operation
of the specialized VFSes that do require it.
*/
        BMN_VERBOSE_IO(
                "FILE CONTROL=> going to sync. master: %s",
                (const char*)pArg);
        break;
    case SQLITE_FCNTL_COMMIT_PHASETWO:
        /* 22
The SQLITE_FCNTL_COMMIT_PHASETWO opcode is generated internally by SQLite and
sent to the VFS after a transaction has been committed immediately but before
the database is unlocked. VFSes that do not need this signal should silently
ignore this opcode. Applications should not call sqlite3_file_control() with
this opcode as doing so may disrupt the operation of the specialized VFSes
that do require it.
*/
        BMN_VERBOSE_IO("FILE CONTROL=> commit second phase");
        break;
    case SQLITE_FCNTL_PDB:
        /* 30
  no description here
  pArg is pointer to  db (sqlite3* type)
  */
        BMN_VERBOSE_IO("FILE CONTROL=>PDB");
        break;
    default:
        BMN_VERBOSE_IO("FILE CONTROL=> operation: %d", iOperation);
        break;
    }
    return rc;
}

#if BMN_OVERRIDE_SLEEP
extern int callSleepMethod(PyObject* pObject, int nMicro)
{
    BMN_TRACE_MARK;

    int rc, ec;
    PyGILState_STATE gilstate;
    PyObject* pResult;
    _Py_IDENTIFIER(sleep);

    rc       = BMN_CB_RESULT_NO_HANDLER;
    gilstate = PyGILState_Ensure();
    pResult  = _PyObject_CallMethodId(pObject, &PyId_sleep, "I", nMicro);
    if(pResult)
    {
        parseResultCode(pResult, &rc);
        Py_DECREF(pResult);
        pResult = NULL;
    }
    ec = BMN_CATCH_PY_EXCEPTION(pObject, "sleep");
    if(BMN_ATTRIBUTE_ERROR == ec)
    {
        rc = BMN_CB_RESULT_NO_HANDLER;
    }
    else if(ec)
    {
        rc = BMN_CB_RESULT_HANDLER_LOGIC_ERROR;
    }
    PyGILState_Release(gilstate);
    return rc;
}
#endif

extern int callGetLastErrorMethod(PyObject* pObject, int nBuf, char* zBuf)
{
    /* ( from unix part)
     ** The xGetLastError() method is designed to return a better
     ** low-level error message when operating-system problems come up
     ** during SQLite operation.  Only the integer return code is currently
     ** used.
     */
    BMN_VERBOSE_INT(nBuf);
    // strncpy(zBuf,"Testing",nBuf);
    // return SQLITE_OK;
    // return SQLITE_MISUSE;
    return BMN_CB_RESULT_NO_HANDLER;
}

extern int callGetCurrentTime(PyObject* pObject, double* fTime)
{
    BMN_TRACE_MARK;

    int rc;
    PyGILState_STATE gilstate;
    PyObject* pResult;
    _Py_IDENTIFIER(current_time);

    rc       = BMN_CB_RESULT_NO_HANDLER;
    gilstate = PyGILState_Ensure();
    pResult  = _PyObject_CallMethodId(pObject, &PyId_current_time, NULL);
    if(pResult)
    {
        if(PyFloat_Check(pResult))
        {
            *fTime = PyFloat_AS_DOUBLE(pResult);
        }
        else if(Py_None == pResult)
        {
            rc = BMN_CB_RESULT_NO_HANDLER;
        }
        else
        {
            RAISE_WRONG_RETURN_TYPE(pObject, "current_time");
            rc = BMN_CB_RESULT_UNEXPECTED_RETURNS;
        }
        Py_DECREF(pResult);
        pResult = NULL;
    }
    else
    {
        int ec;
        ec = BMN_CATCH_PY_EXCEPTION(pObject, "current_time");
        if(BMN_ATTRIBUTE_ERROR == ec)
        {
            rc = BMN_CB_RESULT_NO_HANDLER;
        }
        else if(ec)
        {
            rc = BMN_CB_RESULT_HANDLER_LOGIC_ERROR;
        }
    }
    PyGILState_Release(gilstate);
    return rc;
}

extern int callGetCurrentTimeInt64(PyObject* pObject, sqlite3_int64* pTime)
{
    BMN_TRACE_MARK;
    int rc;
    PyGILState_STATE gilstate;
    PyObject* pResult;
    _Py_IDENTIFIER(current_time_int64);

    rc       = BMN_CB_RESULT_NO_HANDLER;
    gilstate = PyGILState_Ensure();
    pResult  = _PyObject_CallMethodId(pObject, &PyId_current_time_int64, NULL);
    if(pResult)
    {
        if(PyLong_Check(pResult))
        {
            *pTime = PyLong_AsLongLong(pResult);
            rc     = SQLITE_OK;
        }
        else if(PyFloat_Check(pResult))
        {
            *pTime = (sqlite3_int64)PyFloat_AS_DOUBLE(pResult);
            rc     = SQLITE_OK;
        }
        else if(Py_None == pResult)
        {
            rc = BMN_CB_RESULT_NO_HANDLER;
        }
        else
        {
            RAISE_WRONG_RETURN_TYPE(pObject, "current_time_int64");
            rc = BMN_CB_RESULT_UNEXPECTED_RETURNS;
        }
        Py_DECREF(pResult);
        pResult = NULL;
    }
    else
    {
        int ec;
        ec = BMN_CATCH_PY_EXCEPTION(pObject, "current_time_int64");
        if(BMN_ATTRIBUTE_ERROR == ec)
        {
            rc = BMN_CB_RESULT_NO_HANDLER;
        }
        else if(ec)
        {
            rc = BMN_CB_RESULT_HANDLER_LOGIC_ERROR;
        }
    }
    PyGILState_Release(gilstate);
    return rc;
}

/*
 partial methods
*/

// temporary storage
static BmnvfsFile* pPartialFile = NULL;

static int prepareBuffer(void** pBuffer, sqlite3_uint64 iSize)
{
    BMN_ASSERT(pBuffer);
    if(BMN_MEM_SIZE(*pBuffer) < (sqlite3_uint64)iSize)
    {
        *pBuffer = BMN_MEM_REALLOC64(*pBuffer, iSize);
    }
    if(!*pBuffer)
    {
        return SQLITE_NOMEM;
    }
    else
    {
        memset(*pBuffer, 0, iSize);
    }
    return SQLITE_OK;
}

typedef struct MemoryBuffer MemoryBuffer;
struct MemoryBuffer
{
    char* pBuffer;
    Py_ssize_t nLength;
};

static int bytesConverter(PyObject* obj, MemoryBuffer* buffer)
{
    return PyBytes_AsStringAndSize(obj, &buffer->pBuffer, &buffer->nLength) ? 0
                                                                            : 1;
}

// avoid acquiring GIL or something! you're already locked
static PyObject* rawWriteImpl(PyObject* obj, PyObject* args)
{
    BMN_TRACE_MARK;

    sqlite_int64 iOffset;
    MemoryBuffer buffer;
    int rc;

    if(!PyArg_ParseTuple(args, "O&L", bytesConverter, &buffer, &iOffset))
    {
        BMN_ERROR("Can't parse arguments");
        return NULL;
    }
#if BMN_DEBUG_FILENAME_CONTROL
    BMN_VERBOSE_IO(
            "raw write %d by %d to %s",
            buffer.nLength,
            iOffset,
            pPartialFile->zFName);
#endif
    BMN_ASSERT(pPartialFile->pReal);
    BMN_ASSERT(pPartialFile->pReal->pMethods);
    if(iOffset < 0)
    {
        RAISE_VALUE_ERROR(
                NULL,
                "encode",
                "Negative offset passed to 'encode' method");
        return NULL;
    }
    rc = pPartialFile->pReal->pMethods->xWrite(
            pPartialFile->pReal,
            buffer.pBuffer,
            (int)buffer.nLength,
            iOffset);
    if(rc)
    {
        switch(rc)
        {
        case SQLITE_IOERR_WRITE:
            PyErr_SetString(pysqlite_OperationalError, "IO error");
            break;
        case SQLITE_FULL:
            PyErr_SetString(pysqlite_OperationalError, "Disk is full");
            break;
        default:
            RAISE_WRAPPER_ERROR(NULL, "Unexpected Write failure. Code:(%d)", rc)
            break;
        };
        return NULL;
    }
    Py_RETURN_NONE;
}

// avoid acquiring GIL or something! you're already locked
static PyObject* rawReadImpl(PyObject* obj, PyObject* args)
{
    BMN_TRACE_MARK;
    sqlite_int64 iOffset;
    int iAmt;
    int rc;

    if(!PyArg_ParseTuple(args, "IL", &iAmt, &iOffset))
    {
        BMN_ERROR("Can't parse arguments");
        return NULL;
    }
    if(iAmt < 0)
    {
        RAISE_VALUE_ERROR(
                NULL,
                "decode",
                "Negative read length passed to 'decode' method");
        return NULL;
    }
    if(iOffset < 0)
    {
        RAISE_ERROR(
                PyExc_ValueError,
                NULL,
                "Negative offset passed to 'decode' method");
        return NULL;
    }
    rc = prepareBuffer(&pPartialFile->pBuffer, iAmt);
    if(rc)
    {
        BMN_TRACE_ERROR(rc);
        return PyErr_NoMemory();
    }
    BMN_ASSERT(pPartialFile->pReal);
    BMN_ASSERT(pPartialFile->pBuffer);
#if BMN_DEBUG_FILENAME_CONTROL
    BMN_VERBOSE_IO(
            "raw read %d by %d from %s",
            iAmt,
            iOffset,
            pPartialFile->zFName);
#endif
    rc = pPartialFile->pReal->pMethods->xRead(
            pPartialFile->pReal,
            pPartialFile->pBuffer,
            iAmt,
            iOffset);
    if(SQLITE_IOERR_SHORT_READ == rc)
    {
#if BMN_MARK_SHORT_READ_WITH_BOOL
        Py_RETURN_FALSE;
#else
        Py_RETURN_NONE;
#endif
    }
    return PyBytes_FromStringAndSize(pPartialFile->pBuffer, iAmt);
}

extern int callEncodeMethod(
        BmnvfsFile* pFile,
        const char* zBuf,
        Py_ssize_t iAmt,
        sqlite3_int64 iOfst)
{
    BMN_TRACE_MARK;
    int rc;
    PyObject* pResult;
    PyObject* pFunc;
    PyMethodDef pyMethodDef;
    PyGILState_STATE gilstate;
    _Py_IDENTIFIER(encode);

    pyMethodDef.ml_name  = "";
    pyMethodDef.ml_meth  = rawWriteImpl;
    pyMethodDef.ml_flags = METH_VARARGS;
    pyMethodDef.ml_doc   = NULL;
    pPartialFile         = pFile;
#if BMN_DEBUG_FILENAME_CONTROL
    BMN_VERBOSE_IO("shared file to write:%s", pFile->zFName);
#endif
    rc = SQLITE_OK;
    ;
    gilstate = PyGILState_Ensure();
    pFunc    = PyCFunction_New(&pyMethodDef, NULL);

    pResult = _PyObject_CallMethodId(
            pFile->pInfo->pWrapper,
            &PyId_encode,
            "I O y# L",
            pFile->iFlags,
            pFunc,
            zBuf,
            iAmt,
            iOfst);

    if(pResult)
    {
        // we don't need and expect any results here but we have to inform user
        if(Py_None != pResult)
        {
            EMIT_RESULT_IGNORED_WARNING("encode");
        }
        Py_DECREF(pResult);
        pResult = NULL;
    }
    else
    {
        int ec;
        ec = BMN_CATCH_PY_EXCEPTION(pFile->pInfo->pWrapper, "encode");
        if(BMN_ATTRIBUTE_ERROR == ec)
        {
            rc = BMN_CB_RESULT_NO_HANDLER;
            RAISE_NO_MANDATORY_METHOD(pFile->pInfo->pWrapper, "encode");
        }
        else if(ec)
        {
            rc = BMN_CB_RESULT_HANDLER_LOGIC_ERROR;
        }
    }
    // Py_DECREF(pFunc);
    Py_CLEAR(pFunc);
    PyGILState_Release(gilstate);
    return rc;
}

extern int callDecodeMethod(
        BmnvfsFile* pFile,
        char* zBuf,
        Py_ssize_t iAmt,
        sqlite3_int64 iOfst)
{
    BMN_TRACE_MARK;
    int rc;
    PyGILState_STATE gilstate;
    PyObject* pResult;
    PyObject* pFunc;
    _Py_IDENTIFIER(decode);
    PyMethodDef pyMethodDef;
    Py_ssize_t iResultLen;

    pyMethodDef.ml_name  = "";
    pyMethodDef.ml_meth  = rawReadImpl;
    pyMethodDef.ml_flags = METH_VARARGS;
    pyMethodDef.ml_doc   = NULL;
    pPartialFile         = pFile;
#if BMN_DEBUG_FILENAME_CONTROL
    BMN_VERBOSE_IO("shared file to read:%s", pFile->zFName);
#endif
    rc       = SQLITE_OK;
    gilstate = PyGILState_Ensure();
    pFunc    = PyCFunction_New(&pyMethodDef, NULL);

    pResult = _PyObject_CallMethodId(
            pFile->pInfo->pWrapper,
            &PyId_decode,
            "I O I L",
            pFile->iFlags,
            pFunc,
            iAmt,
            iOfst);

    if(pResult)
    {
#if BMN_MARK_SHORT_READ_WITH_BOOL
        if(PyBool_Check(pResult))
        {
            BMN_VERBOSE("Bool 'decode' result");
            memset(zBuf, 0, iAmt);
            rc = SQLITE_IOERR_SHORT_READ;
        }
        else if(Py_None == pResult)
        {
            RAISE_TYPE_ERROR(
                    pFile->pInfo->pWrapper,
                    "Method 'decode' returned None");
            rc = BMN_CB_RESULT_UNEXPECTED_RETURNS;
        }
#else
        if(Py_None == pResult)
        {
            BMN_VERBOSE("None 'deocde' result");
            memset(zBuf, 0, iAmt);
            rc = SQLITE_IOERR_SHORT_READ;
        }
#endif
        else if(PyBytes_Check(pResult))
        {
            iResultLen = PyBytes_GET_SIZE(pResult);
            if(iResultLen <= iAmt)
            {
                memcpy(zBuf, PyBytes_AS_STRING(pResult), iResultLen);
                rc = SQLITE_OK;
            }
            else
            {
                BMN_ERROR(
                        "Bad decode result size:%d instead %d",
                        iResultLen,
                        iAmt);
                rc = BMN_CB_RESULT_UNEXPECTED_RETURNS;
                RAISE_VALUE_ERROR(
                        pFile->pInfo->pWrapper,
                        "decode",
                        "Method 'decode' returned wrong number of bytes");
            }
        }
        else
        {
            BMN_ERROR("Bad decode result type");
            rc = SQLITE_IOERR_READ;
        }
        Py_DECREF(pResult);
        pResult = NULL;
    }
    else
    {
        int ec;
        ec = BMN_CATCH_PY_EXCEPTION(pFile->pInfo->pWrapper, "decode");
        if(BMN_ATTRIBUTE_ERROR == ec)
        {
            rc = BMN_CB_RESULT_NO_HANDLER;
            RAISE_NO_MANDATORY_METHOD(pFile->pInfo->pWrapper, "decode");
        }
        else if(ec)
        {
            rc = BMN_CB_RESULT_HANDLER_LOGIC_ERROR;
        }
    }
    Py_DECREF(pFunc);
    PyGILState_Release(gilstate);
    return rc;
}
