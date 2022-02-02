
#ifndef BMN_DEBUG_H
#define BMN_DEBUG_H

#ifdef NDEBUG
#define BMN_TRACE(...) (void)0;
#define BMN_VTRACE(...) (void)0;
#define BMN_TRACE_INT(...) (void)0;
#define BMN_TRACE_STR(...) (void)0;
#define BMN_TRACE_P(...) (void)0;
#define BMN_WARNING BMN_TRACE
#define BMN_ERROR(...) (void)0;
#define BMN_VERROR(...) (void)0;
#define BMN_VERBOSE_IO(...) (void)0;
#define BMN_VERBOSE_ERROR(...) (void)0;
#define BMN_TRACE_ERROR(...) (void)0;
#define BMN_TRACE_MARK (void)0;
#define BMN_VERBOSE(...) (void)0;
#define BMN_VERBOSE_INT(...) (void)0;
#define BMN_VERBOSE_INT64(...) (void)0;
#define BMN_VERBOSE_P(...) (void)0;
#define BMN_VERBOSE_HEX(...) (void)0;
#define BMN_ASSERT(...) (void)0;
#define BMN_ASSERT_X(...) (void)0;
#define BMN_ASSERT_XY(...) (void)0;
#define BMN_ASSERT_EQUAL(...) (void)0;
#define BMN_ASSERT_REFCOUNT(...) (void)0;
#define BMN_REFCOUNT(...) (void)0;
#else
#include <stdarg.h>
#include <stdlib.h>

#ifndef __FUNCTION_NAME__
#ifdef WIN32
#define __FUNCTION_NAME__ __FUNCTION__
#else
#define __FUNCTION_NAME__ __func__
#endif
#endif

#ifndef BMN_SHOW_TRACE_MARKS
#define BMN_SHOW_TRACE_MARKS 1
#endif

#ifndef BMN_VERBOSE_TRACING
#define BMN_VERBOSE_TRACING 1
#endif

#ifndef BMN_IO_TRACING
#define BMN_IO_TRACING 1
#endif
/*
too annoying
*/
#ifndef _WIN32
#pragma GCC diagnostic ignored "-Wunused-function"
#endif

/*
Level:
0 - plain
1 - error
2 - IO
*/
void bmnPrintf(const char *zFile, int nLine, const char *zFuncname, int nLevel,
               const char *zFormat, ...);
void bmnVPrintf(const char *zFile, int nLine, const char *zFuncname, int nLevel,
                const char *zFormat, va_list va);
int bmnPrintErrCode(int rc, const char *zFile, int nLine,
                    const char *zFuncname);

#define BMN_TRACE(...) \
    bmnPrintf(__FILE__, __LINE__, __FUNCTION_NAME__, 0, __VA_ARGS__)
#define BMN_VTRACE(FMT, VA) \
    bmnVPrintf(__FILE__, __LINE__, __FUNCTION_NAME__, 0, FMT, VA)
#define BMN_WARNING BMN_TRACE

#define BMN_TRACE_INT(X) \
    bmnPrintf(__FILE__, __LINE__, __FUNCTION_NAME__, 0, #X ": %d", (X))
#define BMN_TRACE_STR(X) \
    bmnPrintf(__FILE__, __LINE__, __FUNCTION_NAME__, 0, #X ": %s", (X))
#define BMN_TRACE_INT64(X) \
    bmnPrintf(__FILE__, __LINE__, __FUNCTION_NAME__, 0, #X ": %lld", (X))
#define BMN_TRACE_P(X) \
    bmnPrintf(__FILE__, __LINE__, __FUNCTION_NAME__, 0, #X " pointer: %p", (X))

#if BMN_IO_TRACING
#define BMN_VERBOSE_IO(...) \
    bmnPrintf(__FILE__, __LINE__, __FUNCTION_NAME__, 2, __VA_ARGS__)
#else
#define BMN_VERBOSE_IO(...) (void)0;
#endif

#if BMN_VERBOSE_TRACING
#define BMN_VERBOSE BMN_TRACE
#define BMN_VERBOSE_INT BMN_TRACE_INT
#define BMN_VERBOSE_P BMN_TRACE_P
#define BMN_VERBOSE_ERROR BMN_TRACE_ERROR
#define BMN_VERBOSE_HEX(X) \
    bmnPrintf(__FILE__, __LINE__, __FUNCTION_NAME__, 0, #X ": %x", (X))
#else
#define BMN_VERBOSE(...) (void)0;
#define BMN_VERBOSE_INT(...) (void)0;
#define BMN_VERBOSE_P(...) (void)0;
#define BMN_VERBOSE_HEX(...) (void)0;
#endif

#define BMN_ERROR(...) \
    bmnPrintf(__FILE__, __LINE__, __FUNCTION_NAME__, 1, __VA_ARGS__)
#define BMN_VERROR(FMT, VA) \
    bmnVPrintf(__FILE__, __LINE__, __FUNCTION_NAME__, 1, FMT, VA)

#if BMN_SHOW_TRACE_MARKS
#define BMN_TRACE_MARK \
    bmnPrintf(__FILE__, __LINE__, "trace mark:", 0, __FUNCTION_NAME__)
#else
#define BMN_TRACE_MARK (void)0;
#endif

#define BMN_ASSERT_XY(X, M, M1)                                                  \
    if (!(X)) {                                                                  \
        BMN_ERROR("Assertion at (%s[%d]): %s => '%s' & '%s'", __FUNCTION_NAME__, \
                  __LINE__, #X, (M), (M1));                                      \
        abort();                                                                 \
    }

#define BMN_ASSERT_X(X, M)                                                \
    if (!(X)) {                                                           \
        BMN_ERROR("Assertion at (%s[%d]): %s => '%s'", __FUNCTION_NAME__, \
                  __LINE__, #X, (M));                                     \
        abort();                                                          \
    }

#define BMN_ASSERT(X)                                                            \
    if (!(X)) {                                                                  \
        BMN_ERROR("Assertion at (%s[%d]): %s", __FUNCTION_NAME__, __LINE__, #X); \
        abort();                                                                 \
    }

#define BMN_ASSERT_EQUAL(X, Y)                                                     \
    if ((X) != (Y)) {                                                              \
        BMN_ERROR("Not equal assertion at (%s[%d])!! %d != %d", __FUNCTION_NAME__, \
                  __LINE__, X, Y);                                                 \
        abort();                                                                   \
    }

#define BMN_TRACE_ERROR(rc) \
    bmnPrintErrCode(rc, __FILE__, __LINE__, __FUNCTION_NAME__)
#define BMN_REFCOUNT(OBJ) (int)Py_REFCNT(OBJ)
#define BMN_ASSERT_REFCOUNT(OBJ, COUNT) \
    BMN_ASSERT_EQUAL(BMN_REFCOUNT(OBJ), (COUNT))
#endif
#endif