
/* io.h - definitions for the io wrapper type
 *
 * Copyright(C) 2021-2021 meth
 */

#ifndef BMNSQLITE_VFS_H
#define BMNSQLITE_VFS_H
#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include "utils.h"

/*
returns 0 un success and other value on errors
*/
int bmnVfsRegister(PyObject* pWrapper, int iMakeDefault);

PyObject* bmnFindVfs(const char* zVfsName);

#if REGISTER_DEBUG_ITEMS
PyObject* bmnConnectionCount();
PyObject* bmnFlags();
#endif

#endif
