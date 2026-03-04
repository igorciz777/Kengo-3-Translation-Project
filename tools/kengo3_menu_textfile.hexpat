struct txt<auto size>
{
	char data[size];
};

struct txt_block{
	u32 type;
	u32 size;
	u32 count;
	u32 unk;
	txt<size> text[count];
};

struct txt_entry{
	u32 start;
	u32 size;
	txt_block block @ start;
};

struct txt_file{
	u32 file_size;
	u32 block_count;
	txt_entry entries[block_count];
};

txt_file file @ 0x0;