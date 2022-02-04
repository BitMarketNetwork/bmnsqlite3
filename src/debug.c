#include "debug.h"

#ifndef NDEBUG
#    include <stdio.h>

#    include "bindings.h"
#    include "utils.h"
#    include "sqlite3.h"

#    if defined(_WIN32)
#        include <Windows.h>

int gettimeofday(struct timeval* tv, void* tz)
{
    if(tv)
    {
        FILETIME filetime; /* 64-bit value representing the number of
                              100-nanosecond intervals since January 1, 1601
                              00:00 UTC */
        ULARGE_INTEGER x;
        ULONGLONG usec;
        static const ULONGLONG epoch_offset_us =
                11644473600000000ULL; /* microseconds between Jan 1,1601 and Jan
                                       * 1,1970
                                       */

#        if _WIN32_WINNT >= _WIN32_WINNT_WIN8
        GetSystemTimePreciseAsFileTime(&filetime);
#        else
        GetSystemTimeAsFileTime(&filetime);
#        endif
        x.LowPart   = filetime.dwLowDateTime;
        x.HighPart  = filetime.dwHighDateTime;
        usec        = x.QuadPart / 10 - epoch_offset_us;
        tv->tv_sec  = (long)(usec / 1000000ULL);
        tv->tv_usec = (long)(usec % 1000000ULL);
    }
    return 0;
}

#    endif // _WIN32

extern int bmnPrintErrCode(
        int rc,
        const char* zFile,
        int nLine,
        const char* zFuncname)
{
    char zBuf[50];
    char* zVal;
    int nError;
    nError = 1;
    switch(rc)
    {
    case SQLITE_OK:
    case SQLITE_NOTFOUND:
    case SQLITE_BUSY:
        return 0;
    case SQLITE_ERROR:
        zVal = "SQLITE_ERROR";
        break;
    case SQLITE_PERM:
        zVal = "SQLITE_PERM";
        break;
    case SQLITE_ABORT:
        zVal = "SQLITE_ABORT";
        break;
    case SQLITE_NOMEM:
        zVal = "SQLITE_NOMEM";
        break;
    case SQLITE_READONLY:
        zVal = "SQLITE_READONLY";
        break;
    case SQLITE_INTERRUPT:
        zVal = "SQLITE_INTERRUPT";
        break;
    case SQLITE_IOERR:
        zVal = "SQLITE_IOERR";
        break;
    case SQLITE_CORRUPT:
        zVal = "SQLITE_CORRUPT";
        break;
    case SQLITE_FULL:
        zVal = "SQLITE_FULL";
        break;
    case SQLITE_CANTOPEN:
        zVal = "SQLITE_CANTOPEN";
        break;
    case SQLITE_PROTOCOL:
        zVal = "SQLITE_PROTOCOL";
        break;
    case SQLITE_EMPTY:
        zVal = "SQLITE_EMPTY";
        break;
    case SQLITE_SCHEMA:
        zVal = "SQLITE_SCHEMA";
        break;
    case SQLITE_CONSTRAINT:
        zVal = "SQLITE_CONSTRAINT";
        break;
    case SQLITE_MISMATCH:
        zVal = "SQLITE_MISMATCH";
        break;
    case SQLITE_MISUSE:
        zVal = "SQLITE_MISUSE";
        break;
    case SQLITE_NOLFS:
        zVal = "SQLITE_NOLFS";
        break;
    case SQLITE_IOERR_READ:
        zVal = "SQLITE_IOERR_READ";
        break;
    case SQLITE_IOERR_SHORT_READ:
        zVal   = "SQLITE_IOERR_SHORT_READ";
        nError = 0; // it is normal
        break;
    case SQLITE_IOERR_WRITE:
        zVal = "SQLITE_IOERR_WRITE";
        break;
    case SQLITE_IOERR_FSYNC:
        zVal = "SQLITE_IOERR_FSYNC";
        break;
    case SQLITE_IOERR_DIR_FSYNC:
        zVal = "SQLITE_IOERR_DIR_FSYNC";
        break;
    case SQLITE_IOERR_TRUNCATE:
        zVal = "SQLITE_IOERR_TRUNCATE";
        break;
    case SQLITE_IOERR_FSTAT:
        zVal = "SQLITE_IOERR_FSTAT";
        break;
    case SQLITE_IOERR_UNLOCK:
        zVal = "SQLITE_IOERR_UNLOCK";
        break;
    case SQLITE_IOERR_RDLOCK:
        zVal = "SQLITE_IOERR_RDLOCK";
        break;
    case SQLITE_IOERR_DELETE:
        zVal = "SQLITE_IOERR_DELETE";
        break;
    case SQLITE_IOERR_BLOCKED:
        zVal = "SQLITE_IOERR_BLOCKED";
        break;
    case SQLITE_IOERR_NOMEM:
        zVal = "SQLITE_IOERR_NOMEM";
        break;
    case SQLITE_IOERR_ACCESS:
        zVal = "SQLITE_IOERR_ACCESS";
        break;
    case SQLITE_IOERR_CHECKRESERVEDLOCK:
        zVal = "SQLITE_IOERR_CHECKRESERVEDLOCK";
        break;
    case SQLITE_IOERR_LOCK:
        zVal = "SQLITE_IOERR_LOCK";
        break;
    case SQLITE_IOERR_CLOSE:
        zVal = "SQLITE_IOERR_CLOSE";
        break;
    case SQLITE_IOERR_DIR_CLOSE:
        zVal = "SQLITE_IOERR_DIR_CLOSE";
        break;
    case SQLITE_IOERR_SHMOPEN:
        zVal = "SQLITE_IOERR_SHMOPEN";
        break;
    case SQLITE_IOERR_SHMSIZE:
        zVal = "SQLITE_IOERR_SHMSIZE";
        break;
    case SQLITE_IOERR_SHMLOCK:
        zVal = "SQLITE_IOERR_SHMLOCK";
        break;
    case SQLITE_IOERR_SHMMAP:
        zVal = "SQLITE_IOERR_SHMMAP";
        break;
    case SQLITE_IOERR_SEEK:
        zVal = "SQLITE_IOERR_SEEK";
        break;
    case SQLITE_IOERR_GETTEMPPATH:
        zVal = "SQLITE_IOERR_GETTEMPPATH";
        break;
    case SQLITE_IOERR_CONVPATH:
        zVal = "SQLITE_IOERR_CONVPATH";
        break;
    case SQLITE_READONLY_DBMOVED:
        zVal = "SQLITE_READONLY_DBMOVED";
        break;
    case SQLITE_LOCKED_SHAREDCACHE:
        zVal = "SQLITE_LOCKED_SHAREDCACHE";
        break;
    case SQLITE_BUSY_RECOVERY:
        zVal = "SQLITE_BUSY_RECOVERY";
        break;
    case SQLITE_CANTOPEN_NOTEMPDIR:
        zVal = "SQLITE_CANTOPEN_NOTEMPDIR";
        break;
    // BMN STUFF
    case BMN_CB_RESULT_HANDLER_LOGIC_ERROR:
        zVal = "BMN ERROR: python implementation user error";
        break;
    case BMN_CB_RESULT_NO_HANDLER:
        zVal   = "BMN WARNING: no callback detected";
        nError = 0; // it is almost normal
        break;
    default:
        {
            sqlite3_snprintf(sizeof(zBuf), zBuf, "%d", rc);
            zVal = zBuf;
            break;
        }
    }
#    if !BMN_VERBOSE_TRACING
    if(!nError)
    {
        return 1;
    }
#    endif
    bmnPrintf(
            zFile,
            nLine,
            zFuncname,
            nError,
            "SQLITE ERROR '%s' (%d)",
            zVal,
            rc);
    return 1;
}

extern void bmnVPrintf(
        const char* zFile,
        int nLine,
        const char* zFuncname,
        int nLevel,
        const char* zFormat,
        va_list va)
{
    struct timeval time;
    char const* zLastSlash;
    gettimeofday(&time, NULL);
    // there's no something like strrpbrk in C
    zLastSlash = strrchr(zFile, '\\');
    if(!zLastSlash)
    {
        zLastSlash = strrchr(zFile, '/');
    }
    if(!zLastSlash)
    {
        zLastSlash = zFile;
    }
    if(1 == nLevel)
    {
        fprintf(stderr, "!!! ERROR !!! ");
    }
    else if(2 == nLevel)
    {
        fprintf(stderr, "!!! IO !!! ");
    }
    fprintf(stderr,
            "\t--BMN < %s:%d - %s > [%02u:%03u]-",
            ++zLastSlash,
            nLine,
            zFuncname,
            (unsigned)time.tv_sec % 60,
            (unsigned)(time.tv_usec * 0.001));
    vfprintf(stderr, zFormat, va);
    fprintf(stderr, "--\n");
}
extern void bmnPrintf(
        const char* zFile,
        int nLine,
        const char* zFuncname,
        int nLevel,
        const char* zFormat,
        ...)
{
    va_list argptr;
    va_start(argptr, zFormat);
    bmnVPrintf(zFile, nLine, zFuncname, nLevel, zFormat, argptr);
    va_end(argptr);
}
#endif
