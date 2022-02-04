#ifndef BMN_UTILS_H
#define BMN_UTILS_H
#include "Python.h"
#include "sqlite3.h"

#define BMN_SQLITE_OFFSET \
    -1000 /* error code offset. it must be negative to distinguish it from \
             real values in some callbacks */
#define BMN_CB_RESULT_HANDLER_LOGIC_ERROR \
    BMN_SQLITE_OFFSET - 1 /* user python implementation error (with \
                             implemented callback!) */
#define BMN_CB_RESULT_UNEXPECTED_RETURNS \
    BMN_SQLITE_OFFSET - 2 /* wrong type returned */
#define BMN_CB_RESULT_NO_HANDLER \
    BMN_SQLITE_OFFSET - 3 /* there is no callback */
#define BMN_CB_RESULT_OK 0

#define BMN_CALLBACK_ERROR \
    SQLITE_MISUSE /* what error we return to be handled by pysqlite correctly \
                   */
#define SQLITE_DEFAULT_DEVICE_CHARACTERISTICS SQLITE_IOCAP_UNDELETABLE_WHEN_OPEN

#ifndef SQLITE_BMNVFS_BUFFERSZ
#    define SQLITE_BMNVFS_BUFFERSZ 8192
#endif

/*
hahdle short read with Bool or None
*/
#ifndef BMN_MARK_SHORT_READ_WITH_BOOL
#    define BMN_MARK_SHORT_READ_WITH_BOOL 1
#endif

/*
    Close opened connections when user changes wrapper
*/
#ifndef BMN_CLOSE_CONNECTION_ON_REGISTER
#    define BMN_CLOSE_CONNECTION_ON_REGISTER 1
#endif

/*
    Allow to implement xSleep in python code

    There is no use to implement it in python, but it could lead to
    hard debugging cases
*/
#ifndef BMN_OVERRIDE_SLEEP
#    define BMN_OVERRIDE_SLEEP 0
#endif

/*
  Save last exception location and pass it to python API
  Only for testing purposes
*/
#ifndef BMN_SAVE_EXCEPTION_LOCATION
#    define BMN_SAVE_EXCEPTION_LOCATION 1
#endif

/*
  It's enough
*/
#ifndef BMN_MAX_VFS_NAME_LENGTH
#    define BMN_MAX_VFS_NAME_LENGTH 256
#endif

/*
** The default size of a disk sector
* from sqlite3.c
*/
#ifndef SQLITE_DEFAULT_SECTOR_SIZE
#    define SQLITE_DEFAULT_SECTOR_SIZE 4096
#endif

/*
  memory macroses
  make it abstract in case to change it easily
  toggle sqlite3 / python

  also we going to add leaks-debugging set of macroses
*/

#ifndef BMN_MEM_SQLITE_BACKEND
#    define BMN_MEM_SQLITE_BACKEND 1
#endif

#if BMN_MEM_SQLITE_BACKEND
#    define BMN_MEM_MALLOC(SIZE)         sqlite3_malloc(SIZE)
#    define BMN_MEM_MALLOC64(SIZE)       sqlite3_malloc64(SIZE)
#    define BMN_MEM_REALLOC(PTR, SIZE)   sqlite3_realloc(PTR, SIZE)
#    define BMN_MEM_REALLOC64(PTR, SIZE) sqlite3_realloc64(PTR, SIZE)
#    define BMN_MEM_FREE(PTR)            sqlite3_free(PTR)
#    define BMN_MEM_SIZE(PTR)            sqlite3_msize(PTR)

#    define BMN_MEM_MALLOC_SMALL(SIZE) \
        BMN_MEM_MALLOC(SIZE); \
        BMN_ASSERT(SIZE < 256)
#    define BMN_MEM_REALLOC_SMALL(PTR, SIZE) \
        BMN_MEM_REALLOC(PTR, SIZE); \
        BMN_ASSERT(SIZE < 256)
#    define BMN_MEM_FREE_SMALL(PTR) BMN_MEM_FREE(PTR)
#else
#    define BMN_MEM_MALLOC(SIZE)         PyMem_Malloc(SIZE)
#    define BMN_MEM_MALLOC64(SIZE)       PyMem_Malloc(SIZE)
#    define BMN_MEM_REALLOC(PTR, SIZE)   PyMem_Realloc(PTR, SIZE)
#    define BMN_MEM_REALLOC64(PTR, SIZE) PyMem_Realloc(PTR, SIZE)
#    define BMN_MEM_FREE(PTR)            PyMem_Free(PTR)
#    define BMN_MEM_SIZE(PTR)            PyMem_Free(PTR)
#    define BMN_MEM_SIZE(PTR)            #    error "No PyMem size"

#    define BMN_MEM_MALLOC_SMALL(SIZE) \
        PyObject_Malloc(SIZE); \
        BMN_ASSERT(SIZE < 256)
#    define BMN_MEM_REALLOC_SMALL(PTR, SIZE) \
        PyObject_Realloc(PTR, SIZE); \
        BMN_ASSERT(SIZE < 256)
#    define BMN_MEM_FREE_SMALL(PTR) PyObject_Free(PTR)
#endif

#ifndef NDEBUG
/*
    to control memory leaks and python references
*/
#    define DEBUG_LEAKS_CONTROL        0
/*
    saving filename to debug
*/
#    define BMN_DEBUG_FILENAME_CONTROL 1
#else
#    define DEBUG_LEAKS_CONTROL        0
#    define BMN_DEBUG_FILENAME_CONTROL 0
#    undef BMN_SAVE_EXCEPTION_LOCATION
#    define BMN_SAVE_EXCEPTION_LOCATION 0
#endif

#if BMN_DEBUG_FILENAME_CONTROL
#    define BMN_IO_TRACING 1
#endif

#ifndef NDEBUG
#    define REGISTER_DEBUG_ITEMS 1
#else
#    define REGISTER_DEBUG_ITEMS 0
#endif
/*
    wrapper state  flags
*/
#define BMN_DEFAULT_VFS                        1 << 0 // reserved
#define BMN_NO_CALLBACK_OPEN                   1 << 1
#define BMN_NO_CALLBACK_ACCESS                 1 << 2
#define BMN_NO_CALLBACK_DELETE                 1 << 3
#define BMN_NO_CALLBACK_RANDOM                 1 << 4
#define BMN_NO_CALLBACK_DEVICE_CHARACTERISTICS 1 << 5
#define BMN_NO_CALLBACK_SECTOR_SIZE            1 << 6
#define BMN_NO_CALLBACK_SYNC                   1 << 7
#define BMN_NO_CALLBACK_FILE_CONTROL           1 << 8
#if BMN_OVERRIDE_SLEEP
#    define BMN_NO_CALLBACK_SLEEP 1 << 9
#endif
#define BMN_NO_CALLBACK_FULL_PATHNAME 1 << 10
#if 0 == BMN_MARK_SHORT_READ_WITH_BOOL
#    define BMN_READ_REAL_WORK \
        1 << 10 /* it means read/decode hasn't returned short read error */
#endif

/*
  wrappper check result code
*/
#define BMN_WRAPPER_CHECK_RESULT_OK           0
#define BMN_WRAPPER_CHECK_RESULT_ERROR_PASS   1
#define BMN_WRAPPER_CHECK_RESULT_ERROR_RAISED 2
#define BMN_WRAPPER_CHECK_RESULT_NONE_WRAPPER 3

#define RAISE_ERROR(EXC, OBJ, ...) \
    BMN_ERROR(__VA_ARGS__); \
    PyErr_Format((EXC), __VA_ARGS__); \
    if(OBJ) \
    { \
        PyErr_WriteUnraisable((OBJ)); \
    }

#define RAISE_TYPE_ERROR(OBJ, ...) \
    RAISE_ERROR(PyExc_TypeError, (OBJ), __VA_ARGS__)

#define RAISE_VALUE_ERROR(OBJ, METH, ...) \
    RAISE_ERROR(PyExc_ValueError, (OBJ), __VA_ARGS__) \
    saveLocation((OBJ), (METH))

#define RAISE_OVERFLOW_ERROR(OBJ, ...) \
    RAISE_ERROR(PyExc_OverflowError, (OBJ), __VA_ARGS__)

#define RAISE_NAME_ERROR(OBJ, ...) \
    RAISE_ERROR(PyExc_NameError, (OBJ), __VA_ARGS__)

#define RAISE_NOT_IMPLEMENTED_ERROR(OBJ, ...) \
    RAISE_ERROR(PyExc_NotImplementedError, (OBJ), __VA_ARGS__)

#define RAISE_WRAPPER_ERROR(OBJ, ...) \
    RAISE_ERROR(pysqlite_WrapperError, (OBJ), __VA_ARGS__)

typedef struct BmnvfsHolder BmnvfsHolder;
typedef struct BmnvfsFile BmnvfsFile;
typedef struct BmnvfsInfo BmnvfsInfo;
typedef struct BmnvfsNode BmnvfsNode;

struct BmnvfsHolder
{
    int iFileSize;
};

struct BmnvfsNode
{
    sqlite3_file* file;
    BmnvfsNode* next;
    BmnvfsNode* prev;
};

struct BmnvfsInfo
{
    sqlite3_vfs* pRootVfs;
    PyObject* pWrapper;
    int iFlags;

#if BMN_CLOSE_CONNECTION_ON_REGISTER
    BmnvfsNode* pFiles;
#    if DEBUG_LEAKS_CONTROL
    /*
actually it may be mirrors opened files
but:
1/ may be not
2/ it'll be removed
3/ it'is different compile modes
*/
    int iAllocatedNodes;
#    endif
#else
    int iOpenedFiles;
#endif
};

struct BmnvfsFile
{
    sqlite3_file base;
    BmnvfsInfo* pInfo;
    int iFlags;
#if BMN_DEBUG_FILENAME_CONTROL
    const char* zFName;
#endif
    sqlite3_file* pReal;
    PyObject* pFileWrapper;
    /*
 mempool to avoid multiple allocations
 used only in partial impl.
 */
    void* pBuffer;
};

/*
pay attention. we call it 'title' as opposed of 'name', cause 'name' of wrapper
will have a little bit another meaning in next releases
*/
const char* getObjectTypename(PyObject* pWrapper);

int openedConnectionsCount(BmnvfsInfo* pInfo);

int checkWrapperObject(PyObject* pObject);

void saveLocation(PyObject* pObject, const char* zLocation);

int initPyModule();

#endif
