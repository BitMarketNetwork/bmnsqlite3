#include "vfs.h"

#include <fcntl.h>
#include <string.h>

#include "bindings.h"
#include "debug.h"
#include "utils.h"

#define BMNVFS_NAME "bmn_vfs"

/*
 ** It can be tweaked in future
 */
#define BMN_FILE(p) ((BmnvfsFile*)(void*)p)
#define BMN_INFO(p) ((BmnvfsInfo*)(void*)p->pAppData)
#define BMN_VFS(p)  ((BmnvfsInfo*)(void*)p->pAppData)->pRootVfs

static BmnvfsInfo staticInfo;
static sqlite3_vfs staticVfs;
extern PyObject* pysqlite_WrapperError;
extern PyObject* pysqlite_OperationalError;

/*
** Method declarations for BmnvfsFile.
*/
static int bmnvfsClose(sqlite3_file*);
static int bmnvfsRead(sqlite3_file*, void*, int iAmt, sqlite3_int64 iOfst);
static int bmnvfsWrite(
        sqlite3_file*,
        const void*,
        int iAmt,
        sqlite3_int64 iOfst);
static int bmnvfsTruncate(sqlite3_file*, sqlite3_int64 size);
static int bmnvfsSync(sqlite3_file*, int flags);
static int bmnvfsFileSize(sqlite3_file*, sqlite3_int64* pSize);
static int bmnvfsLock(sqlite3_file*, int);
static int bmnvfsUnlock(sqlite3_file*, int);
static int bmnvfsCheckReservedLock(sqlite3_file*, int*);
static int bmnvfsFileControl(sqlite3_file*, int iOperation, void* pArg);
static int bmnvfsSectorSize(sqlite3_file*);
static int bmnvfsDeviceCharacteristics(sqlite3_file*);
static int bmnvfsShmLock(sqlite3_file*, int, int, int);
static int bmnvfsShmMap(sqlite3_file*, int, int, int, void volatile**);
static void bmnvfsShmBarrier(sqlite3_file*);
static int bmnvfsShmUnmap(sqlite3_file*, int);
static int bmnvfsFetch(sqlite3_file*, sqlite3_int64, int, void**);
static int bmnvfsUnfetch(sqlite3_file*, sqlite3_int64, void*);
static int bmnvfsShmLock(sqlite3_file*, int, int, int);
// Method declarations for bmnvfs_vfs.
static int bmnvfsOpen(sqlite3_vfs*, const char*, sqlite3_file*, int, int*);
static int bmnvfsDelete(sqlite3_vfs*, const char* zName, int syncDir);
static int bmnvfsAccess(sqlite3_vfs*, const char* zName, int flags, int*);
static int bmnvfsFullPathname(sqlite3_vfs*, const char* zName, int, char* zOut);
#ifndef SQLITE_OMIT_LOAD_EXTENSION
static void* bmnvfsDlOpen(sqlite3_vfs*, const char* zFilename);
static void bmnvfsDlError(sqlite3_vfs*, int nByte, char* zErrMsg);
static void (*bmnvfsDlSym(sqlite3_vfs*, void*, const char* zSymbol))(void);
static void bmnvfsDlClose(sqlite3_vfs*, void*);
#endif /* SQLITE_OMIT_LOAD_EXTENSION */
static int bmnvfsRandomness(sqlite3_vfs*, int nByte, char* zOut);
static int bmnvfsSleep(sqlite3_vfs*, int microseconds);
static int bmnvfsCurrentTime(sqlite3_vfs*, double*);
static int bmnvfsGetLastError(sqlite3_vfs*, int, char*);
static int bmnvfsCurrentTimeInt64(sqlite3_vfs*, sqlite3_int64*);
static int bmnvfsSetSystemCall(sqlite3_vfs*, const char*, sqlite3_syscall_ptr);
static sqlite3_syscall_ptr bmnvfsGetSystemCall(sqlite3_vfs*, const char* z);
static const char* bmnvfsNextSystemCall(sqlite3_vfs*, const char* zName);

#ifndef NDEBUG
static const char* fileName(const char* z)
{
    int i;
    if(z == 0)
        return 0;
    i = (int)strlen(z) - 1;
    while(i > 0 && z[i - 1] != '/')
    {
        i--;
    }
    return &z[i];
}
#endif
// Open an bmnvfs file handle.
static int bmnvfsOpen(
        sqlite3_vfs* pVfs,
        const char* zName,
        sqlite3_file* pFile,
        int flags,
        int* pOutFlags)
{
    BMN_TRACE_MARK;
    int rc;
    BmnvfsFile* pBmnFile = BMN_FILE(pFile);
    BmnvfsInfo* pInfo    = BMN_INFO(pVfs);
    sqlite3_io_methods* pNewSet;

    // TODO: not sure
    if(zName == 0)
    {
        return SQLITE_IOERR;
    }

    pNewSet = BMN_MEM_MALLOC_SMALL(sizeof(*pNewSet));
    memset(pNewSet, 0, sizeof(*pNewSet));
    pNewSet->iVersion               = 1; // pVfs->iVersion;
    pNewSet->xClose                 = bmnvfsClose;
    pNewSet->xRead                  = bmnvfsRead;
    pNewSet->xWrite                 = bmnvfsWrite;
    pNewSet->xTruncate              = bmnvfsTruncate;
    pNewSet->xSync                  = bmnvfsSync;
    pNewSet->xFileSize              = bmnvfsFileSize;
    pNewSet->xLock                  = bmnvfsLock;
    pNewSet->xUnlock                = bmnvfsUnlock;
    pNewSet->xCheckReservedLock     = bmnvfsCheckReservedLock;
    pNewSet->xFileControl           = bmnvfsFileControl;
    pNewSet->xSectorSize            = bmnvfsSectorSize;
    pNewSet->xDeviceCharacteristics = bmnvfsDeviceCharacteristics;
    if(pVfs->iVersion >= 1)
    {
        pNewSet->xShmMap     = bmnvfsShmMap;
        pNewSet->xShmLock    = bmnvfsShmLock;
        pNewSet->xShmBarrier = bmnvfsShmBarrier;
        pNewSet->xShmUnmap   = bmnvfsShmUnmap;
    }
    if(pNewSet->iVersion >= 2)
    {
        pNewSet->xFetch   = bmnvfsFetch;
        pNewSet->xUnfetch = bmnvfsUnfetch;
    }

    BMN_VERBOSE_INT(pInfo->iFlags);
    BMN_VERBOSE(
            "Opening %s (%p)",
            zName ? fileName(zName) : "[tmp]",
            pOutFlags);
#if BMN_DEBUG_FILENAME_CONTROL
    pBmnFile->zFName = zName ? fileName(zName) : "[tmp]";
#endif
    rc = BMN_CB_RESULT_NO_HANDLER;
    if(0 == (pInfo->iFlags & BMN_NO_CALLBACK_OPEN))
    {
        rc = callOpenMethod(pInfo->pWrapper, pBmnFile, zName, flags, pOutFlags);
    }

    BMN_VERBOSE(
            "Using  %s mode",
            BMN_CB_RESULT_NO_HANDLER == rc ? "partial" : "full");
    if(BMN_CB_RESULT_NO_HANDLER == rc)
    {
        pInfo->iFlags |= BMN_NO_CALLBACK_OPEN;
        sqlite3_vfs* pRoot     = pInfo->pRootVfs;
        pBmnFile->pReal        = (sqlite3_file*)&pBmnFile[1];
        // once again  to be clear
        pBmnFile->pFileWrapper = NULL;
        pBmnFile->iFlags       = flags;
        rc = pRoot->xOpen(pRoot, zName, pBmnFile->pReal, flags, pOutFlags);
        BMN_ASSERT(!pBmnFile->pFileWrapper);
        BMN_VERBOSE_HEX(flags);
    }
    else if(BMN_CB_RESULT_HANDLER_LOGIC_ERROR == rc)
    {
        BMN_TRACE_ERROR(rc);
        return BMN_CALLBACK_ERROR;
    }
    else if(0 != rc)
    {
        BMN_TRACE_ERROR(rc);
        return SQLITE_CANTOPEN;
    }
    else
    {
        pBmnFile->pReal = NULL;
    }
    pBmnFile->base.pMethods = pNewSet;
    pBmnFile->pInfo         = pInfo;
#if BMN_CLOSE_CONNECTION_ON_REGISTER
    BmnvfsNode** temp;
    BmnvfsNode* prev;
    temp = &pInfo->pFiles;
    prev = NULL;
    while(*temp)
    {
        prev = *temp;
        temp = &(*temp)->next;
    }
    *temp = (BmnvfsNode*)BMN_MEM_MALLOC_SMALL(sizeof(BmnvfsNode));
#    if DEBUG_LEAKS_CONTROL
    ++pInfo->iAllocatedNodes;
    BMN_TRACE("########### NODES COUNT %d", pInfo->iAllocatedNodes);
#    endif
    (*temp)->file = pFile;
    (*temp)->next = NULL;
    (*temp)->prev = prev;
#else
    pInfo->iOpenedFiles += 1;
#endif
    BMN_ASSERT(pBmnFile->pReal || pBmnFile->pFileWrapper);
    return rc;
}

/*
** Close a BmnvfsFile
*/
static int bmnvfsCloseImpl(sqlite3_file* pFile)
{
    BMN_TRACE_MARK;
    int rc;
    rc = SQLITE_OK;
    BmnvfsFile* pBmnFile;
    pBmnFile = BMN_FILE(pFile);
    if(pBmnFile->pFileWrapper)
    {
        rc = callCloseMethod(pBmnFile->pInfo->pWrapper, pBmnFile);
        if(rc)
        {
            rc = BMN_CALLBACK_ERROR;
        }
    }
    else
    {
        BMN_ASSERT(pBmnFile->pReal);
        if(pBmnFile->pReal->pMethods)
        {
            rc = pBmnFile->pReal->pMethods->xClose(pBmnFile->pReal);
        }
    }
    BMN_TRACE_ERROR(rc);
    if(rc == SQLITE_OK)
    {
        BMN_MEM_FREE_SMALL((void*)pBmnFile->base.pMethods);
        pBmnFile->base.pMethods = NULL;
    }
    return rc;
}
static int bmnvfsClose(sqlite3_file* pFile)
{
    BMN_TRACE_MARK;
    int rc;
    BmnvfsFile* pBmnFile;
    pBmnFile = BMN_FILE(pFile);
    rc       = bmnvfsCloseImpl(pFile);
#if BMN_CLOSE_CONNECTION_ON_REGISTER
    BMN_ASSERT(pBmnFile->pInfo);
    BmnvfsNode** temp = &pBmnFile->pInfo->pFiles;
    BmnvfsNode* prev  = NULL;
#    if DEBUG_LEAKS_CONTROL
    int deleted = 0;
    int count   = openedConnectionsCount(pBmnFile->pInfo);
#    endif
    while(*temp)
    {
        if(pFile == (*temp)->file)
        {
            BmnvfsNode* next = (*temp)->next;
            if(next)
            {
                next->prev = prev;
            }
            BMN_MEM_FREE_SMALL(*temp);
            *temp = next;
#    if DEBUG_LEAKS_CONTROL
            --pBmnFile->pInfo->iAllocatedNodes;
            BMN_ASSERT(pBmnFile->pInfo->iAllocatedNodes >= 0);
            BMN_TRACE(
                    "########### NODES COUNT %d",
                    pBmnFile->pInfo->iAllocatedNodes);
            deleted = 1;
#    endif
            break;
        }
        prev = *temp;
        temp = &(*temp)->next;
    }
#    if DEBUG_LEAKS_CONTROL
    BMN_ASSERT(deleted);
    BMN_ASSERT_EQUAL(openedConnectionsCount(pBmnFile->pInfo), count - 1);
#    endif
#else
    pBmnFile->pInfo->iOpenedFiles -= 1;
#endif
    return rc;
}

static int bmnvfsDelete(sqlite3_vfs* pVfs, const char* zName, int syncDir)
{
    /*
        Deletion must be called anyway !!!
        Hard to debug
    */
    BMN_TRACE_MARK;
    int rc;
    BmnvfsInfo* pInfo = BMN_INFO(pVfs);
    rc                = BMN_CB_RESULT_NO_HANDLER;
    if(0 == (pInfo->iFlags & BMN_NO_CALLBACK_DELETE))
    {
        rc = callDeleteMethod(pInfo->pWrapper, zName, syncDir);
    }
    if(BMN_CB_RESULT_NO_HANDLER == rc)
    {
        pInfo->iFlags |= BMN_NO_CALLBACK_DELETE;
        rc = pInfo->pRootVfs->xDelete(pInfo->pRootVfs, zName, syncDir);
    }
    else if(BMN_CB_RESULT_HANDLER_LOGIC_ERROR == rc)
    {
        // pInfo->iCallbackFlags |= BMN_NO_CALLBACK_DELETE;
        rc = BMN_CALLBACK_ERROR;
    }
    BMN_TRACE_ERROR(rc);
    return rc;
}

static int bmnvfsAccess(
        sqlite3_vfs* pVfs,
        const char* zName,
        int flags,
        int* pResOut)
{
    BMN_TRACE_MARK;
    int rc;
    BmnvfsInfo* pInfo = BMN_INFO(pVfs);
    rc                = BMN_CB_RESULT_NO_HANDLER;
    // BMN_VERBOSE_INT(pInfo->iCallbackFlags);
    if(0 == (pInfo->iFlags & BMN_NO_CALLBACK_ACCESS))
    {
        rc = callAccessMethod(pInfo->pWrapper, zName, flags, pResOut);
    }
    if(BMN_CB_RESULT_NO_HANDLER == rc)
    {
        rc = pInfo->pRootVfs->xAccess(pInfo->pRootVfs, zName, flags, pResOut);
        pInfo->iFlags |= BMN_NO_CALLBACK_ACCESS;
    }
    else if(rc < 0)
    {
        // rc = SQLITE_IOERR_ACCESS;
        rc = BMN_CALLBACK_ERROR;
    }
    BMN_VERBOSE("Access result for %s is %d", zName, *pResOut);
    BMN_TRACE_ERROR(rc);
    return rc;
}

static int bmnvfsFullPathname(
        sqlite3_vfs* pVfs,
        const char* zName,
        int nOut,
        char* zOut)
{
    BMN_TRACE_MARK;
    int rc;
    BmnvfsInfo* pInfo = BMN_INFO(pVfs);
    rc                = BMN_CB_RESULT_NO_HANDLER;
    if(0 == (pInfo->iFlags & BMN_NO_CALLBACK_FULL_PATHNAME))
    {
        rc = callFullPathname(pInfo->pWrapper, zName, nOut, zOut);
    }
    if(BMN_CB_RESULT_NO_HANDLER == rc)
    {
        pInfo->iFlags |= BMN_NO_CALLBACK_FULL_PATHNAME;
        rc = pInfo->pRootVfs->xFullPathname(pInfo->pRootVfs, zName, nOut, zOut);
    }
    else if(rc < 0)
    {
        rc = BMN_CALLBACK_ERROR;
        strncpy(zOut, zName, nOut);
    }
    BMN_TRACE_ERROR(rc);
    return rc;
}

static int bmnvfsRandomness(sqlite3_vfs* pVfs, int nByte, char* zOut)
{
    BMN_TRACE_MARK;
    int rc;
    BmnvfsInfo* pInfo = BMN_INFO(pVfs);
    rc                = BMN_CB_RESULT_NO_HANDLER;
    if(0 == (pInfo->iFlags & BMN_NO_CALLBACK_RANDOM))
    {
        rc = callRandomnessMethod(pInfo->pWrapper, nByte, zOut);
    }
    if(rc < 0)
    {
        pInfo->iFlags |= BMN_NO_CALLBACK_RANDOM;
        rc = pInfo->pRootVfs->xRandomness(pInfo->pRootVfs, nByte, zOut);
        BMN_VERBOSE("random result length: %d", rc);
    }
    return rc;
}

static int bmnvfsSleep(sqlite3_vfs* pVfs, int nMicro)
{
    BmnvfsInfo* pInfo = BMN_INFO(pVfs);
#if BMN_OVERRIDE_SLEEP
    BMN_TRACE_MARK;
    int rc;
    rc = BMN_CB_RESULT_NO_HANDLER;

    if(0 == (pInfo->iFlags & BMN_NO_CALLBACK_SLEEP))
    {
        rc = callSleepMethod(pInfo->pWrapper, nMicro);
    }
    if(BMN_CB_RESULT_NO_HANDLER == rc)
    {
        pInfo->iFlags |= BMN_NO_CALLBACK_SLEEP;
        rc = pInfo->pRootVfs->xSleep(pInfo->pRootVfs, nMicro);
    }
    else if(rc < 0)
    {
        rc = BMN_CALLBACK_ERROR;
    }
    return rc;
#endif
    return pInfo->pRootVfs->xSleep(pInfo->pRootVfs, nMicro);
}

static int bmnvfsGetLastError(sqlite3_vfs* pVfs, int nBuf, char* zBuf)
{
    BMN_TRACE_MARK;
    int rc;
    BmnvfsInfo* pInfo = BMN_INFO(pVfs);
    rc                = callGetLastErrorMethod(pInfo->pWrapper, nBuf, zBuf);
    if(BMN_CB_RESULT_NO_HANDLER == rc)
    {
        rc = pInfo->pRootVfs->xGetLastError(pInfo->pRootVfs, nBuf, zBuf);
    }
    return rc;
}
static int bmnvfsCurrentTime(sqlite3_vfs* pVfs, double* fTime)
{
    BMN_TRACE_MARK;
    int rc;
    BmnvfsInfo* pInfo = BMN_INFO(pVfs);
    rc                = callGetCurrentTime(pInfo->pWrapper, fTime);
    if(BMN_CB_RESULT_NO_HANDLER == rc)
    {
        rc = pInfo->pRootVfs->xCurrentTime(pInfo->pRootVfs, fTime);
    }
    else if(rc < 0)
    {
        rc = BMN_CALLBACK_ERROR;
    }
    BMN_TRACE_ERROR(rc);
    return rc;
}
static int bmnvfsCurrentTimeInt64(sqlite3_vfs* pVfs, sqlite3_int64* pTime)
{
    BMN_TRACE_MARK;
    int rc;
    BmnvfsInfo* pInfo = BMN_INFO(pVfs);
    rc                = callGetCurrentTimeInt64(pInfo->pWrapper, pTime);
    if(BMN_CB_RESULT_NO_HANDLER == rc)
    {
        BMN_TRACE_MARK;
        rc = pInfo->pRootVfs->xCurrentTimeInt64(pInfo->pRootVfs, pTime);
    }
    else if(rc < 0)
    {
        rc = BMN_CALLBACK_ERROR;
    }
    BMN_TRACE_ERROR(rc);
    return rc;
}
static int bmnvfsSetSystemCall(
        sqlite3_vfs* pVfs,
        const char* zName,
        sqlite3_syscall_ptr pCall)
{
    BMN_TRACE_MARK;
    return BMN_VFS(pVfs)->xSetSystemCall(BMN_VFS(pVfs), zName, pCall);
}
static sqlite3_syscall_ptr bmnvfsGetSystemCall(
        sqlite3_vfs* pVfs,
        const char* zName)
{
    BMN_TRACE_MARK;
    return BMN_VFS(pVfs)->xGetSystemCall(BMN_VFS(pVfs), zName);
}
static const char* bmnvfsNextSystemCall(sqlite3_vfs* pVfs, const char* zName)
{
    BMN_TRACE_MARK;
    return BMN_VFS(pVfs)->xNextSystemCall(BMN_VFS(pVfs), zName);
}

static void* bmnvfsDlOpen(sqlite3_vfs* pVfs, const char* zFilename)
{
    BMN_TRACE_MARK;
    return BMN_VFS(pVfs)->xDlOpen(BMN_VFS(pVfs), zFilename);
}
static void bmnvfsDlError(sqlite3_vfs* pVfs, int nByte, char* zErrMsg)
{
    BMN_TRACE_MARK;
    BMN_VFS(pVfs)->xDlError(BMN_VFS(pVfs), nByte, zErrMsg);
}
static void (*bmnvfsDlSym(sqlite3_vfs* pVfs, void* pMem, const char* zSymbol))(
        void)
{
    BMN_TRACE_MARK;
    return BMN_VFS(pVfs)->xDlSym(BMN_VFS(pVfs), pMem, zSymbol);
}
static void bmnvfsDlClose(sqlite3_vfs* pVfs, void* pHandle)
{
    BMN_TRACE_MARK;
    BMN_VFS(pVfs)->xDlClose(BMN_VFS(pVfs), pHandle);
}

static int bmnvfsRead(
        sqlite3_file* pFile,
        void* zBuf,
        int iAmt,
        sqlite_int64 iOfst)
{
    BMN_TRACE_MARK;
    int rc;
    BmnvfsFile* pBmnFile = BMN_FILE(pFile);
    if(pBmnFile->pFileWrapper)
    {
        rc = callReadMethod(pBmnFile->pInfo, pBmnFile, zBuf, iAmt, iOfst);
    }
    else
    {
        // BMN_VERBOSE("decode len:%d offset:%d", iAmt, iOfst);
        BMN_ASSERT(pBmnFile->pReal);
        rc = callDecodeMethod(pBmnFile, zBuf, iAmt, iOfst);
#if BMN_DEBUG_FILENAME_CONTROL
        if(rc && SQLITE_IOERR_SHORT_READ != rc)
        {
            BMN_ERROR(
                    "File: %s , flag: %d",
                    pBmnFile->zFName,
                    pBmnFile->iFlags);
        }
#endif
    }
    if(rc < BMN_SQLITE_OFFSET)
    {
        rc = BMN_CALLBACK_ERROR;
    }
    BMN_TRACE_ERROR(rc);
    return rc;
}

static int bmnvfsWrite(
        sqlite3_file* pFile,
        const void* zBuf,
        int iAmt,
        sqlite3_int64 iOfst)
{
    BMN_TRACE_MARK;
    int rc;
    BmnvfsFile* pBmnFile = BMN_FILE(pFile);
    if(pBmnFile->pFileWrapper)
    {
        rc = callWriteMethod(
                pBmnFile->pInfo->pWrapper,
                pBmnFile,
                zBuf,
                iAmt,
                iOfst);
    }
    else
    {
        BMN_VERBOSE("encode len:%d offset:%d", iAmt, iOfst);
        BMN_ASSERT(pBmnFile->pReal);
        rc = callEncodeMethod(pBmnFile, zBuf, iAmt, iOfst);
        BMN_TRACE_ERROR(rc);
#if BMN_DEBUG_FILENAME_CONTROL
        if(rc)
        {
            BMN_ERROR(
                    "File: %s , flag: %d",
                    pBmnFile->zFName,
                    pBmnFile->iFlags);
        }
#endif
    }
    if(rc < BMN_SQLITE_OFFSET)
    {
        rc = BMN_CALLBACK_ERROR;
    }
    BMN_TRACE_ERROR(rc);
    return rc;
}
static int bmnvfsTruncate(sqlite3_file* pFile, sqlite3_int64 size)
{
    BMN_TRACE_MARK;
    int rc;
    BmnvfsFile* pBmnFile = BMN_FILE(pFile);
    if(pBmnFile->pFileWrapper)
    {
        rc = callFileTruncateMethod(pBmnFile->pInfo->pWrapper, pBmnFile, size);
        if(BMN_CB_RESULT_NO_HANDLER == rc)
        {
            rc = BMN_CALLBACK_ERROR;
        }
        else if(BMN_CB_RESULT_HANDLER_LOGIC_ERROR == rc)
        {
            rc = BMN_CALLBACK_ERROR;
        }
    }
    else
    {
        BMN_ASSERT(pBmnFile->pReal);
        rc = pBmnFile->pReal->pMethods->xTruncate(pBmnFile->pReal, size);
    }
    BMN_TRACE_ERROR(rc);
    return rc;
}
/*
    can be missed
*/
static int bmnvfsSync(sqlite3_file* pFile, int flags)
{
    BMN_TRACE_MARK;
    int rc;
    BmnvfsFile* pBmnFile = BMN_FILE(pFile);
    rc                   = BMN_CB_RESULT_NO_HANDLER;
    if(pBmnFile->pFileWrapper)
    {
        if(0 == (pBmnFile->pInfo->iFlags & BMN_NO_CALLBACK_SYNC))
        {
            rc = callSyncMethod(pBmnFile->pInfo->pWrapper, pBmnFile, flags);
        }
        if(BMN_CB_RESULT_NO_HANDLER == rc)
        {
            pBmnFile->pInfo->iFlags |= BMN_NO_CALLBACK_SYNC;
            rc = SQLITE_OK;
        }
        else if(BMN_CB_RESULT_HANDLER_LOGIC_ERROR == rc)
        {
            pBmnFile->pInfo->iFlags |= BMN_NO_CALLBACK_SYNC;
            rc = BMN_CALLBACK_ERROR;
        }
    }
    else
    {
        BMN_ASSERT(pBmnFile->pReal);
        rc = pBmnFile->pReal->pMethods->xSync(pBmnFile->pReal, flags);
        BMN_TRACE_ERROR(rc);
    }
    BMN_TRACE_ERROR(rc);
    return rc;
}
/*
    must have method
*/
static int bmnvfsFileSize(sqlite3_file* pFile, sqlite3_int64* pSize)
{
    BMN_TRACE_MARK;
    int rc;
    BmnvfsFile* pBmnFile = BMN_FILE(pFile);
    if(pBmnFile->pFileWrapper)
    {
        rc = callFileSizeMethod(pBmnFile->pInfo->pWrapper, pBmnFile, pSize);
        if(rc < 0)
        {
            rc     = BMN_CALLBACK_ERROR;
            *pSize = 0;
        }
    }
    else
    {
        BMN_ASSERT(pBmnFile->pReal);
        rc = pBmnFile->pReal->pMethods->xFileSize(pBmnFile->pReal, pSize);
    }
    BMN_TRACE_ERROR(rc);
    return rc;
}
static int bmnvfsLock(sqlite3_file* pFile, int flags)
{
    BMN_TRACE_MARK;
    int rc;
    BmnvfsFile* pBmnFile = BMN_FILE(pFile);
    if(pBmnFile->pFileWrapper)
    {
        rc = SQLITE_OK;
    }
    else
    {
        BMN_ASSERT(pBmnFile->pReal);
        rc = pBmnFile->pReal->pMethods->xLock(pBmnFile->pReal, flags);
    }
    BMN_TRACE_ERROR(rc);
    return rc;
}
static int bmnvfsUnlock(sqlite3_file* pFile, int flags)
{
    BMN_TRACE_MARK;
    int rc;
    BmnvfsFile* pBmnFile = BMN_FILE(pFile);
    if(pBmnFile->pFileWrapper)
    {
        rc = SQLITE_OK;
    }
    else
    {
        BMN_ASSERT(pBmnFile->pReal);
        rc = pBmnFile->pReal->pMethods->xUnlock(pBmnFile->pReal, flags);
    }
    BMN_TRACE_ERROR(rc);
    return rc;
}
static int bmnvfsCheckReservedLock(sqlite3_file* pFile, int* pResOut)
{
    BMN_TRACE_MARK;
    int rc;
    BmnvfsFile* pBmnFile = BMN_FILE(pFile);
    if(pBmnFile->pFileWrapper)
    {
        // rc = SQLITE_LOCKED;
        rc = SQLITE_OK;
    }
    else
    {
        BMN_ASSERT(pBmnFile->pReal);
        rc = pBmnFile->pReal->pMethods->xCheckReservedLock(
                pBmnFile->pReal,
                pResOut);
    }
    BMN_TRACE_ERROR(rc);
    return rc;
}
static int bmnvfsFileControl(sqlite3_file* pFile, int iOperation, void* pArg)
{
    BMN_TRACE_MARK;
    int rc;
    BmnvfsFile* pBmnFile = BMN_FILE(pFile);
    if(pBmnFile->pFileWrapper)
    {
        rc = SQLITE_NOTFOUND;
        BMN_VERBOSE_INT(iOperation);
        if(0 == (pBmnFile->pInfo->iFlags & BMN_NO_CALLBACK_FILE_CONTROL))
        {
            rc = callFileControlMethod(
                    pBmnFile->pInfo->pWrapper,
                    pBmnFile,
                    iOperation,
                    pArg);
        }
        // be carefull
        if(BMN_CB_RESULT_NO_HANDLER == rc)
        {
            pBmnFile->pInfo->iFlags |= BMN_NO_CALLBACK_FILE_CONTROL;
            rc = SQLITE_NOTFOUND;
        }
        else if(rc < 0)
        {
            rc = BMN_CALLBACK_ERROR;
        }
    }
    else
    {
        BMN_ASSERT(pBmnFile->pReal);
        rc = pBmnFile->pReal->pMethods->xFileControl(
                pBmnFile->pReal,
                iOperation,
                pArg);
    }
    BMN_TRACE_ERROR(rc);
    return rc;
}
static int bmnvfsSectorSize(sqlite3_file* pFile)
{
    BMN_TRACE_MARK;
    int rc;
    BmnvfsFile* pBmnFile = BMN_FILE(pFile);
    if(pBmnFile->pFileWrapper)
    {
        rc = BMN_CB_RESULT_NO_HANDLER;
        if(0 == (pBmnFile->pInfo->iFlags & BMN_NO_CALLBACK_SECTOR_SIZE))
        {
            rc = callSectorSizeMethod(pBmnFile->pInfo->pWrapper, pBmnFile);
        }
        if(rc < 0)
        {
            pBmnFile->pInfo->iFlags |= BMN_NO_CALLBACK_SECTOR_SIZE;
            rc = SQLITE_DEFAULT_SECTOR_SIZE;
        }
    }
    else
    {
        BMN_ASSERT(pBmnFile->pReal);
        rc = pBmnFile->pReal->pMethods->xSectorSize(pBmnFile->pReal);
    }
    BMN_VERBOSE_INT(rc);
    return rc;
}

static int bmnvfsDeviceCharacteristics(sqlite3_file* pFile)
{
    BMN_TRACE_MARK;
    int rc;
    BmnvfsFile* pBmnFile = BMN_FILE(pFile);
    if(pBmnFile->pFileWrapper)
    {
        rc = SQLITE_DEFAULT_DEVICE_CHARACTERISTICS;
        if(0 ==
           (pBmnFile->pInfo->iFlags & BMN_NO_CALLBACK_DEVICE_CHARACTERISTICS))
        {
            rc = callDeviceCharacteristicsMethod(
                    pBmnFile->pInfo->pWrapper,
                    pBmnFile);
        }
        if(rc < 0)
        {
            // we can't return error so handle in the same way everything
            pBmnFile->pInfo->iFlags |= BMN_NO_CALLBACK_DEVICE_CHARACTERISTICS;
            rc = SQLITE_DEFAULT_DEVICE_CHARACTERISTICS;
        }
    }
    else
    {
        BMN_ASSERT(pBmnFile->pReal);
        rc = pBmnFile->pReal->pMethods->xDeviceCharacteristics(pBmnFile->pReal);
    }
    BMN_VERBOSE_INT(rc);
    return rc;
}

static int bmnvfsFetch(
        sqlite3_file* pFile,
        sqlite3_int64 nSize,
        int nArg,
        void** zBuf)
{
    BMN_TRACE_MARK;
    return BMN_FILE(pFile)->pReal->pMethods->xFetch(pFile, nSize, nArg, zBuf);
}

static int bmnvfsUnfetch(sqlite3_file* pFile, sqlite3_int64 nSize, void* zBuf)
{
    BMN_TRACE_MARK;
    return BMN_FILE(pFile)->pReal->pMethods->xUnfetch(pFile, nSize, zBuf);
}
static int bmnvfsShmLock(sqlite3_file* pFile, int nOffset, int n, int flags)
{
    BMN_TRACE_MARK;
    return BMN_FILE(pFile)->pReal->pMethods->xShmLock(pFile, nOffset, n, flags);
}

static int bmnvfsShmMap(
        sqlite3_file* pFile,
        int iRegion,
        int szRegion,
        int isWrite,
        void volatile** pp)
{
    BMN_TRACE_MARK;
    return BMN_FILE(pFile)
            ->pReal->pMethods->xShmMap(pFile, iRegion, szRegion, isWrite, pp);
}

static void bmnvfsShmBarrier(sqlite3_file* pFile)
{
    BMN_TRACE_MARK;
    BMN_FILE(pFile)->pReal->pMethods->xShmBarrier(pFile);
}
static int bmnvfsShmUnmap(sqlite3_file* pFile, int delFlag)
{
    BMN_TRACE_MARK;
    return BMN_FILE(pFile)->pReal->pMethods->xShmUnmap(pFile, delFlag);
}

extern int bmnVfsRegister(PyObject* pWrapper, int iMakeDefault)
{
    sqlite3_vfs* pOld;
    sqlite3_vfs* pRoot;
    sqlite3_vfs* pNew;
    BmnvfsInfo* pInfo;
    int rc;

    pOld = sqlite3_vfs_find(BMNVFS_NAME);

    if(pOld)
    {
        pInfo = BMN_INFO(pOld);
        if(pInfo->pWrapper == pWrapper)
        {
            BMN_VERBOSE(
                    "The same wrapper. Skip vfs register for %s",
                    getObjectTypename(pWrapper));
            return 0;
        }
#if BMN_CLOSE_CONNECTION_ON_REGISTER
        /*
unwind this stack from the top
*/
#    if DEBUG_LEAKS_CONTROL
        BMN_ASSERT_EQUAL(openedConnectionsCount(pInfo), pInfo->iAllocatedNodes);
#    endif
        BmnvfsNode* pNode = pInfo->pFiles;
        BmnvfsNode* pPrev = NULL;
        if(pNode)
        {
            while(pNode->next)
            {
                pNode = pNode->next;
            }
            // pNode is top now
            while(pNode)
            {
                pPrev = pNode->prev;
                bmnvfsCloseImpl(pNode->file);
                BMN_MEM_FREE_SMALL(pNode);
                pNode = pPrev;
#    if DEBUG_LEAKS_CONTROL
                --pInfo->iAllocatedNodes;
#    endif
            }
        }
        pInfo->pFiles = NULL;
#    if DEBUG_LEAKS_CONTROL
        BMN_ASSERT_EQUAL(pInfo->iAllocatedNodes, 0);
        BMN_TRACE("########### NODES COUNT %d", pInfo->iAllocatedNodes);
#    endif
#else
        BMN_VERBOSE_INT(pInfo->iOpenedFiles);
        if(pInfo->iOpenedFiles > 0)
        {
            PyErr_Format(
                    pysqlite_OperationalError,
                    "There are %d files still opened with '%s' wrapper. Close "
                    "all connections before making new wrapper registration",
                    pInfo->iOpenedFiles,
                    getWrapperTitle(pInfo->pWrapper));
            return -1;
        }
#endif

        pRoot = pInfo->pRootVfs;
        // Py_DECREF(pInfo->pWrapper);
    }
    else
    {
        pRoot = sqlite3_vfs_find(NULL);
    }
    if(!pRoot)
    {
        BMN_ERROR("there is no default vfs");
        return -1;
    }

    if(Py_None == pWrapper)
    {
        BMN_TRACE("unregister io wrapper");
        if(pOld)
        {
            pInfo = BMN_INFO(pOld);
            BMN_ASSERT(pInfo);
            Py_XDECREF(pInfo->pWrapper);
            if(sqlite3_vfs_unregister(pOld))
            {
                BMN_ERROR("unregistering error");
                return -1;
            }
            rc = sqlite3_vfs_register(pInfo->pRootVfs, 1);
            BMN_TRACE_ERROR(rc);
            return rc;
        }
        return 0;
    }
    //
    if(checkWrapperObject(pWrapper))
    {
        BMN_ERROR("bad io wrapper object");
        PyErr_SetString(pysqlite_OperationalError, "Invalid VFS wrapper");
        return -1;
    }

    /**
     * flex code approach
     **/
    pNew  = &staticVfs;
    pInfo = &staticInfo;

    /*
    use this case for current_time test coverage

    set it to 0 for it
    */
#if 1
    pNew->iVersion = pRoot->iVersion;
#else
    pNew->iVersion      = 1;
#endif
    pNew->szOsFile = pRoot->szOsFile + sizeof(BmnvfsFile);
#ifndef BMN_DEF_MAXPATHNAME
    pNew->mxPathname = pRoot->mxPathname;
#else
    pNew->mxPathname    = BMN_DEF_MAXPATHNAME
#endif
    pNew->pAppData      = pInfo;
    pNew->xOpen         = bmnvfsOpen;
    pNew->zName         = BMNVFS_NAME;
    pNew->xDelete       = bmnvfsDelete;
    pNew->xAccess       = bmnvfsAccess;
    pNew->xFullPathname = bmnvfsFullPathname;
#ifndef SQLITE_OMIT_LOAD_EXTENSION
    pNew->xDlOpen  = bmnvfsDlOpen;
    pNew->xDlError = bmnvfsDlError;
    pNew->xDlSym   = bmnvfsDlSym;
    pNew->xDlClose = bmnvfsDlClose;
#else
    pNew->xDlOpen       = NULL;
    pNew->xDlError      = NULL;
    pNew->xDlSym        = NULL;
    pNew->xDlClose      = NULL;
#endif /* SQLITE_OMIT_LOAD_EXTENSION */
    pNew->xRandomness       = bmnvfsRandomness;
    pNew->xSleep            = bmnvfsSleep;
    pNew->xCurrentTime      = bmnvfsCurrentTime;
    pNew->xCurrentTimeInt64 = bmnvfsCurrentTimeInt64;
    pNew->xGetLastError     = bmnvfsGetLastError;
    pNew->xSetSystemCall    = bmnvfsSetSystemCall;
    pNew->xGetSystemCall    = bmnvfsGetSystemCall;
    pNew->xNextSystemCall   = bmnvfsNextSystemCall;
    pInfo->pWrapper         = pWrapper;
    pInfo->iFlags           = 0;
    pInfo->pRootVfs         = pRoot;
    if(initPyModule())
    {
        BMN_ERROR("Can't init BMN module");
        BMN_MEM_FREE(pNew);
        return -1;
    }
    // TODO: use iMakeDefault
    rc = sqlite3_vfs_register(pNew, 1);
#if BMN_CLOSE_CONNECTION_ON_REGISTER
    pInfo->pFiles = NULL;
#    if DEBUG_LEAKS_CONTROL
    pInfo->iAllocatedNodes = 0;
#    endif
#else
    pInfo->iOpenedFiles = 0;
#endif
    Py_INCREF(pWrapper);
    BMN_TRACE_ERROR(rc);
    return rc;
}
PyObject* bmnFindVfs(const char* zVfsName)
{
    sqlite3_vfs* pVfs;

    pVfs = sqlite3_vfs_find(BMNVFS_NAME);
    if(pVfs)
    {
        BmnvfsInfo* pInfo;
        pInfo = BMN_INFO(pVfs);
        if(pInfo->pWrapper)
        {
            Py_INCREF(pInfo->pWrapper);
            return pInfo->pWrapper;
        }
    }
    Py_RETURN_NONE;
}

#if REGISTER_DEBUG_ITEMS
extern PyObject* bmnConnectionCount()
{
    sqlite3_vfs* pVfs;

    pVfs = sqlite3_vfs_find(BMNVFS_NAME);
    if(pVfs)
    {
        return PyLong_FromLong(openedConnectionsCount(BMN_INFO(pVfs)));
    }
    Py_RETURN_NONE;
}
extern PyObject* bmnFlags()
{
    sqlite3_vfs* pVfs;

    pVfs = sqlite3_vfs_find(BMNVFS_NAME);
    if(pVfs)
    {
        return PyLong_FromLong(BMN_INFO(pVfs)->iFlags);
    }
    Py_RETURN_NONE;
}
#endif
