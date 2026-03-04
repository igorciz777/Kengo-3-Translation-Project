// Kengo 3 Dialog Text File
struct TextEntry{
    u16 t_unk1;
    u16 size;
    u32 offset; // start of block + 0x10 + offset == start of text
};

struct DataBlock {
    u16 marker;
    u16 blockSize;   
    if(marker == 0x0b){
        u32 type;
        u32 pad;
        u16 param1;
        u16 param2;
        u16 text_count;
        u16 param4;
        u16 d_unk1;
        u16 d_unk2;
        u16 d_unk3;
        u16 d_unk4;
        u16 d_unk5;
        u16 d_unk6;
        u16 d_unk7;
        u16 d_unk8;
        TextEntry texts[text_count];
        u8 data[blockSize - 36 - (8*text_count)];
    }else{
        u8 data[blockSize - 4];
    }
};

struct EntryHeader {
    u32 ehunk1;             // Usually 0x00
    u32 data_count;           // Number of control blocks in this entry
    u32 ehunk2;             // Usually 0x14
    u32 ehunk3;             // Usually 0x14
    u32 ehunk4;             // Usually 0x00
    DataBlock data[data_count];
};

struct Entry {
    u32 eunk0;                
    u32 eunk1;                 // Usually 0x00
    u32 eunk2;                 // Usually 0x00
    u32 eunk3;                   
    u32 offset;               // Absolute offset from file start
    EntryHeader entry @ offset;
};

struct FileHeader {
    u32 entryCount;           // Number of entries
    u32 unknown1;             // Always 0x08
    Entry entries[entryCount];
};

FileHeader file @ 0x0;
//TextBlock text @ 0xd7e;