"""镜像文件格式与 C 数组表示之间的转换。

.vm = 8 字节小端虚拟容量头 + 原始镜像；容量包含执行时预留的栈，
文件中不需要写出这些零填充栈字节。嵌入式入口直接使用原始镜像，不带容量头。
"""

def packer(raw_image : bytes,ratio = 2,fixspace = None,stackspace = None) -> bytes:
    '''
    this packer packs the raw image (with absolute location) 
    into a image that can be loaded by our c4vm loader

    ratio    = (preloaded virtual space) / (.data + .text space)
    fixspace : if ratio is not set, you can set the entire space 
    stackspace : if both above are not set, you may set this just for stack
    '''

    raw_size = len(raw_image)
    if ratio is not None:
        virtual_size = int(raw_size * ratio)
    elif fixspace is not None:
        fixspace : int
        virtual_size = fixspace
    elif stackspace is not None:
        virtual_size = raw_size + stackspace
    else:
        raise ValueError("specify ratio, fixspace, or stackspace")
    if not isinstance(virtual_size, int) or virtual_size < raw_size + 64:
        raise ValueError("virtual space must hold the image plus at least 64 bytes of stack")
    # The VM stack and instruction words are 8 bytes wide.
    virtual_size = (virtual_size + 7) // 8 * 8
    return virtual_size.to_bytes(8, 'little') + raw_image

def qword_array(raw_image: bytes) -> list:
    """按有符号 64 位整数输出镜像字，供生成的 long long code[] 保留原始位模式。"""
    if len(raw_image) % 8:
        raise ValueError("qword image must be aligned to 8 bytes")
    res = []
    for i in range(0,len(raw_image),8):
        qword = raw_image[i:i+8]
        res.append(int.from_bytes(qword,'little',signed=True))
    return res
