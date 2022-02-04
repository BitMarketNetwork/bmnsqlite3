

#ifndef BMN_BINDINGS_H
#define BMN_BINDINGS_H
// https://docs.python.org/3/c-api/intro.html#include-files
#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include "sqlite3.h"

// forward

typedef struct BmnvfsFile BmnvfsFile;
typedef struct BmnvfsInfo BmnvfsInfo;

/*
    pObject is redundant here when we have pFile pointer
    But let it be for order and possible future changes
*/
int callOpenMethod(
        PyObject* pObject,
        BmnvfsFile* pFile,
        const char* zFilename,
        int flags,
        int* pOutFlags);

int callCloseMethod(PyObject* pObject, BmnvfsFile* pFile);

int callFullPathname(
        PyObject* pObject,
        const char* zFilename,
        int nOut,
        char* zOut);

int callDeviceCharacteristicsMethod(PyObject* pObject, BmnvfsFile* pFile);

int callAccessMethod(
        PyObject* pObject,
        const char* zPath,
        int flags,
        int* pResOut);

int callDeleteMethod(PyObject* pObject, const char* zName, int syncDir);

int callReadMethod(
        BmnvfsInfo* pInfo,
        BmnvfsFile* pFile,
        char* zBuf,
        Py_ssize_t iAmt,
        sqlite_int64 iOfst);

int callWriteMethod(
        PyObject* pObject,
        BmnvfsFile* pFile,
        const char* zBuf,
        Py_ssize_t iAmt,
        sqlite_int64 iOfst);

int callFileSizeMethod(
        PyObject* pObject,
        BmnvfsFile* pFile,
        sqlite3_int64* pSize);

int callFileTruncateMethod(
        PyObject* pObject,
        BmnvfsFile* pFile,
        sqlite3_int64 iSize);

int callSyncMethod(PyObject* pObject, BmnvfsFile* pFile, int flags);

int callSectorSizeMethod(PyObject* pObject, BmnvfsFile* pFile);

int callRandomnessMethod(PyObject* pObject, int nByte, char* zByte);

int callFileControlMethod(
        PyObject* pObject,
        BmnvfsFile* pFile,
        int iOperation,
        void* pArg);

#if BMN_OVERRIDE_SLEEP
int callSleepMethod(PyObject* pObject, int nMicro);
#endif

int callGetLastErrorMethod(PyObject* pObject, int nBuf, char* zBuf);

int callGetCurrentTime(PyObject* pObject, double* fTime);

int callGetCurrentTimeInt64(PyObject* pObject, sqlite3_int64* pTime);

/*
 partial methods
*/

int callEncodeMethod(
        BmnvfsFile* pFile,
        const char* zBuf,
        Py_ssize_t iAmt,
        sqlite3_int64 iOfst);

int callDecodeMethod(
        BmnvfsFile* pFile,
        char* zBuf,
        Py_ssize_t iAmt,
        sqlite3_int64 iOfst);

#endif
