// Kengo 3 Menu Text File Format
struct sjis_string<auto max_len> {
    char data[max_len];
};

struct MenuTextBlock {
    u32 type;
    u32 size;               // For type 1: bytes per text entry. Others: varies.
    u32 count;              // Number of entries
    u32 padding;            // Always 0x10
    sjis_string<size> entries[count];
};

struct FileEntry {
    u32 offset;             // Absolute offset to MenuTextBlock
    u32 size;               // Total block data size (including 16-byte header)
};

struct FileHeader {
    u32 file_size;          // Total file size in bytes
    u32 block_count;        // Number of blocks
    FileEntry entries[block_count];
};

FileHeader file @ 0x0;
