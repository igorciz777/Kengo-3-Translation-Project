// Kengo 3 Dialog Text File
struct TextEntry{
    u16 lineFlags;
    u16 slotSize;
    u32 relOffset;
};

struct DataBlock {
    u16 marker;
    u16 blockSize;
    if(marker == 0x0b){
        u32 type;
        u32 pad;
        u16 windowStyle;
        u16 pad2;
        u16 textCount;
        u16 textSize;
        u16 subBlockIdx;
        u16 unk2;
        u16 unk3;
        u16 unk4;
        u16 formatFlag;
        u16 messageId;
        u16 dataFlag;
        u16 dataSize;
        TextEntry texts[textCount];
        u8 textData[blockSize - 36 - (8*textCount)];
    }else{
        u8 data[blockSize - 4];
    }
};

struct EntryHeader {
    u32 unk0;
    u32 blockCount;
    u32 unk2;
    u32 unk3;
    u32 unk4;
    DataBlock blocks[blockCount];
};

struct Entry {
    u32 unk0;
    u32 unk1;
    u32 unk2;
    u32 entryIdx;
    u32 offset;
    EntryHeader entry @ offset;
};

struct FileHeader {
    u32 entryCount;
    u32 magic;
    Entry entries[entryCount];
};

FileHeader file @ 0x0;