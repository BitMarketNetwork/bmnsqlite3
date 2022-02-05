#include "module.h"

#include "debug.h"
#include "sqlite3.h"
#include "vfs.h"

extern PyMODINIT_FUNC PyInit__sqlite3(void);
extern PyObject* pysqlite_DatabaseError;
PyObject* pysqlite_WrapperError   = NULL;
PyObject* pysqlite_WrapperWarning = NULL;

static PyObject* module_vfs_register(
        PyObject* self,
        PyObject* args,
        PyObject* kwargs)
{
    static char* kwlist[] = {"wrapper", "make_default", NULL};
    PyObject* wrapper;
    int make_default;
    int rc;

    make_default = 1;
    if(!PyArg_ParseTupleAndKeywords(
               args,
               kwargs,
               "O|i",
               kwlist,
               &wrapper,
               &make_default))
    {
        return NULL;
    }
    BMN_VERBOSE("VFS default: %d", make_default);

    rc = bmnVfsRegister(wrapper, make_default);
    if(SQLITE_OK != rc)
    {
        return NULL;
    }
    Py_RETURN_NONE;
}
PyDoc_STRVAR(
        module_vfs_register_doc,
        "vfs_register(wrapper)\n\
\n\
Registers class instance *wrapper* to handle pysqlite3 vfs operations.\n\
You should call this method with *None* argument as a wrapper to unregister\n\
vfs operations handling and get back default vfs behavior.\n\
");

static PyObject* module_vfs_find(
        PyObject* self,
        PyObject* args,
        PyObject* kwargs)
{
    static char* kwlist[] = {"vfs_name", NULL};
    char* vfs_name;

    vfs_name = NULL;
    if(!PyArg_ParseTupleAndKeywords(args, kwargs, "|s", kwlist, &vfs_name))
    {
        return NULL;
    }
    return bmnFindVfs(vfs_name);
}
PyDoc_STRVAR(
        module_vfs_find_doc,
        "vfs_find()\n\
\n\
Returns registered vfs wrapper or None.\n\
");

#if REGISTER_DEBUG_ITEMS
static PyObject* module_get_connections_count(PyObject* self)
{
    return bmnConnectionCount();
}
PyDoc_STRVAR(
        module_get_connections_count_doc,
        "connections_count()\n\
\n\
Returns number of opened with current wrapper connections or None.\n\
");
static PyObject* module_get_flags(PyObject* self)
{
    return bmnFlags();
}
PyDoc_STRVAR(
        module_get_flags_doc,
        "flags()\n\
\n\
Returns flags of current wrapper or None.\n\
");
#endif
/**/
static PyMethodDef module_methods[] = {
        {"vfs_register",
         (PyCFunction)module_vfs_register,
         METH_VARARGS | METH_KEYWORDS,
         module_vfs_register_doc},
        {"vfs_find",
         (PyCFunction)module_vfs_find,
         METH_VARARGS | METH_KEYWORDS,
         module_vfs_find_doc},

#if REGISTER_DEBUG_ITEMS
        {"connection_count",
         (PyCFunction)module_get_connections_count,
         METH_NOARGS,
         module_get_connections_count_doc},
        {"flags",
         (PyCFunction)module_get_flags,
         METH_NOARGS,
         module_get_flags_doc},
#endif
        {NULL, NULL}};

PyMODINIT_FUNC PyInit__bmnsqlite3(void)
{
    PyObject *module, *dict;
    module = PyInit__sqlite3();
    if(module)
    {
        if(PyModule_AddStringConstant(module, "version", MODULE_VERSION) < 0)
        {
            Py_DECREF(module);
            return NULL;
        }
        if(PyModule_AddFunctions(module, module_methods) < 0)
        {
            Py_DECREF(module);
            return NULL;
        }
        if(!(dict = PyModule_GetDict(module)))
        {
            Py_DECREF(module);
            return NULL;
        }
        if(!(pysqlite_WrapperError = PyErr_NewException(
                     MODULE_NAME ".WrapperError",
                     pysqlite_DatabaseError,
                     NULL)))
        {
            Py_DECREF(module);
            return NULL;
        }
        PyDict_SetItemString(dict, "WrapperError", pysqlite_WrapperError);
        if(!(pysqlite_WrapperWarning = PyErr_NewException(
                     MODULE_NAME ".WrapperWarning",
                     PyExc_UserWarning,
                     NULL)))
        {
            Py_DECREF(module);
            return NULL;
        }
        PyDict_SetItemString(dict, "WrapperWarning", pysqlite_WrapperWarning);
#if REGISTER_DEBUG_ITEMS
// if(PyModule_AddStringConstant(module,"DEBUG_MODE",))
#endif
    }
    return module;
}
