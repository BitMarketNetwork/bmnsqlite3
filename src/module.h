#pragma once

#define PY_SSIZE_T_CLEAN
#if !defined(PY_SSIZE_T_CLEAN)
#    error It is recommended to always define PY_SSIZE_T_CLEAN.
#endif

#include <Python.h>
