/* io.h - definitions for the io wrapper type
 *
 * Copyright(C) 2021-2021 meth
 */

#pragma once
#include "module.h"

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
