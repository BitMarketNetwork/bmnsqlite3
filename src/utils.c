#include "utils.h"

#include "debug.h"

BmnvfsHolder vfsHolder;
extern PyObject* pysqlite_WrapperError;
extern PyObject* pysqlite_DatabaseError;

#if PY_VERSION_HEX >= 0x03080000
extern int _pysqlite_enable_callback_tracebacks;
#else
int _pysqlite_enable_callback_tracebacks = 1;
#endif

extern const char* getObjectTypename(PyObject* pWrapper)
{
    return Py_TYPE(pWrapper)->tp_name;
}

extern int openedConnectionsCount(BmnvfsInfo* pInfo)
{
#if BMN_CLOSE_CONNECTION_ON_REGISTER
    int iCount        = 0;
    BmnvfsNode* pNode = pInfo->pFiles;
    while(pNode)
    {
        pNode = pNode->next;
        ++iCount;
    }
    return iCount;
#else
    return pInfo->iOpenedFiles;
#endif
}

extern int checkWrapperObject(PyObject* pObject)
{
    BMN_ASSERT(pObject);
    if(PyType_Check(pObject))
    {
        PyErr_Format(
                pysqlite_DatabaseError,
                "Register instance as VFS wrapper instead of class %s",
                getObjectTypename(pObject));
        return 1;
    }
    BMN_TRACE("Wrapper type: %s", Py_TYPE(pObject)->tp_name);
    return 0;
}

extern void saveLocation(PyObject* pObject, const char* zLocation)
{
#if BMN_SAVE_EXCEPTION_LOCATION
    if(pObject)
    {
        if(PyObject_SetAttrString(
                   pObject,
                   "exception_location",
                   PyUnicode_FromString(zLocation)) < 0)
        {
            BMN_ERROR("Can't set exception location");
        }
    }
#endif
}

/**
 *
 * bindings initialization stuff
 *
 * might be called many times!
 * */
extern int initPyModule()
{
#ifndef NDEBUG
    _pysqlite_enable_callback_tracebacks = 1;
#endif
    return 0;
}
