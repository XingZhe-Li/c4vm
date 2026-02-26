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
        return virtual_size.to_bytes(8,'little') + raw_image
    elif fixspace is not None:
        fixspace : int
        return fixspace.to_bytes(8,'little') + raw_image
    elif stackspace is not None:
        return (raw_size + stackspace).to_bytes(8,'little') + raw_image
    return b''

def qword_array(raw_image: bytes) -> list:
    res = []
    for i in range(0,len(raw_image),8):
        qword = raw_image[i:i+8]
        res.append(int.from_bytes(qword,'little',signed=True))
    return res