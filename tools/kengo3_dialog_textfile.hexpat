// Kengo 3 Dialog Text File
struct TextEntry {
    u16 line_flags;
    u16 slot_size;
    u32 rel_offset;
};

struct DataBlock {
    u16 marker;
    u16 block_size;
    if(marker == 0x000B) {
        u32 type;
        u32 padding;
        u16 window_style;
        u16 padding2;
        u16 text_count;
        u16 text_size;
        u16 sub_block_idx;
        u16 unk5;
        u16 unk6;
        u16 unk7;
        u16 format_flag;
        u16 message_id;
        u16 data_flag;
        u16 data_size;
        TextEntry texts[text_count];
        u8 text_data[block_size - 36 - (text_count * 8)];
    } else {
        u8 data[block_size - 4];
    }
};

struct EntryHeader {
    u32 unk0;
    u32 block_count;
    u32 unk2;
    u32 unk3;
    u32 unk4;
    DataBlock blocks[block_count];
};

struct DialogEntry {
    u32 unk0;
    u32 unk1;
    u32 unk2;
    u32 entry_idx;
    u32 offset;
    EntryHeader entry @ offset;
};

struct FileHeader {
    u32 entry_count;
    u32 magic;
    DialogEntry entries[entry_count];
};

FileHeader file @ 0x0;
