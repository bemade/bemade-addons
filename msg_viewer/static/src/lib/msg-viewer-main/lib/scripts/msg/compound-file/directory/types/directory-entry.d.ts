export interface DirectoryEntry {
  /**
   * Directory Entry Name (64 bytes): This field MUST contain a Unicode string for the storage or
   * stream name encoded in UTF-16. The name MUST be terminated with a UTF-16 terminating null
   * character. Thus, storage and stream names are limited to 32 UTF-16 code points, including the
   * terminating null character. When locating an object in the compound file except for the root
   * storage, the directory entry name is compared by using a special case-insensitive uppercase
   * mapping, described in Red-Black Tree. The following characters are illegal and MUST NOT be part
   * of the name: '/', '\', ':', '!'.
   */
  entryName: string,

  /**
   * Directory Entry Name Length (2 bytes): This field MUST match the length of the Directory Entry
   * Name Unicode string in bytes. The length MUST be a multiple of 2 and include the terminating null
   * character in the count. This length MUST NOT exceed 64, the maximum size of the Directory Entry
   * Name field.
   */
  entryNameLength: number,

  /**
   * Object Type (1 byte): This field MUST be 0x00, 0x01, 0x02, or 0x05, depending on the actual type of object. All other values are not valid.
   */
  objectType: ObjectType,

  /**
   * Color Flag (1 byte): This field MUST be 0x00 (red) or 0x01 (black). All other values are not valid
   */
  colorFlag: ColorFlag,

  /**
   * Left Sibling ID (4 bytes): This field contains the stream ID of the left sibling. If there is no left sibling, the field MUST be set to NOSTREAM (0xFFFFFFFF).
   * ---------------------------------------------------------------------------------
   * Value                          | Meaning
   * -------------------------------|-------------------------------------------------
   * REGSID 0x00000000 — 0xFFFFFFF9 | Regular stream ID to identify the directory entry.
   * MAXREGSID 0xFFFFFFFA           | Maximum regular stream ID.
   * NOSTREAM 0xFFFFFFFF            | If there is no left sibling.
   */
  leftSiblingId: number,

  /**
   * Right Sibling ID (4 bytes): This field contains the stream ID of the right sibling. If there is no right sibling, the field MUST be set to NOSTREAM (0xFFFFFFFF).
   * ---------------------------------------------------------------------------------
   * Value                          | Meaning
   * -------------------------------|-------------------------------------------------
   * REGSID 0x00000000 — 0xFFFFFFF9 | Regular stream ID to identify the directory entry.
   * MAXREGSID 0xFFFFFFFA           | Maximum regular stream ID.
   * NOSTREAM 0xFFFFFFFF            | If there is no right sibling.
   */
  rightSiblingId: number,

  /**
   * Child ID (4 bytes): This field contains the stream ID of a child object. If there is no child object, including all entries for stream objects, the field MUST be set to NOSTREAM (0xFFFFFFFF).
   * ---------------------------------------------------------------------------------
   * Value                          | Meaning
   * -------------------------------|-------------------------------------------------
   * REGSID 0x00000000 — 0xFFFFFFF9 | Regular stream ID to identify the directory entry.
   * MAXREGSID 0xFFFFFFFA           | Maximum regular stream ID.
   * NOSTREAM 0xFFFFFFFF            | If there is no child object.
   */
  childId: number,

  /**
   * CLSID (16 bytes): This field contains an object class GUID, if this entry is for a storage object or
   * root storage object. For a stream object, this field MUST be set to all zeroes. A value containing all
   * zeroes in a storage or root storage directory entry is valid, and indicates that no object class is
   * associated with the storage. If an implementation of the file format enables applications to create
   * storage objects without explicitly setting an object class GUID, it MUST write all zeroes by default.
   * If this value is not all zeroes, the object class GUID can be used as a parameter to start
   * applications.
   * 
   * -----------------------------------------------------------------------------------
   * Value                              | Meaning
   * -----------------------------------|-----------------------------------------------
   * 0x00000000000000000000000000000000 | No object class is associated with the storage.
   */
  clsid: string,

  /**
   * State Bits (4 bytes): This field contains the user-defined flags if this entry is for a storage object or
   * root storage object. For a stream object, this field SHOULD be set to all zeroes because many
   * implementations provide no way for applications to retrieve state bits from a stream object. If an
   * implementation of the file format enables applications to create storage objects without explicitly
   * setting state bits, it MUST write all zeroes by default.
   * --------------------------------------------------------------------------------
   * Value       | Meaning
   * ------------|-------------------------------------------------------------------
   * 0x00000000  | Default value when no state bits are explicitly set on the object.
   */
  stateBits: number,

  /**
   * Creation Time (8 bytes): This field contains the creation time for a storage object, or all zeroes to
   * indicate that the creation time of the storage object was not recorded. The Windows FILETIME
   * structure is used to represent this field in UTC. For a stream object, this field MUST be all zeroes.
   * For a root storage object, this field MUST be all zeroes, and the creation time is retrieved or set on
   * the compound file itself.
   * -------------------------------------------------------------------
   * Value               | Meaning
   * --------------------|----------------------------------------------
   * 0x0000000000000000  | No creation time was recorded for the object.
   */
  creationTime: bigint,

  /**
   * Modified Time (8 bytes): This field contains the modification time for a storage object, or all
   * zeroes to indicate that the modified time of the storage object was not recorded. The Windows
   * FILETIME structure is used to represent this field in UTC. For a stream object, this field MUST be
   * all zeroes. For a root storage object, this field MAY<2> be set to all zeroes, and the modified time
   * is retrieved or set on the compound file itself.
   * -------------------------------------------------------------------
   * Value               | Meaning
   * --------------------|----------------------------------------------
   * 0x0000000000000000  | No modified time was recorded for the object.
   */
  modifiedTime: bigint,

  /**
   * Starting Sector Location (4 bytes): This field contains the first sector location if this is a stream
   * object. For a root storage object, this field MUST contain the first sector of the mini stream, if the
   * mini stream exists. For a storage object, this field MUST be set to all zeroes.
   */
  startingSectorLocation: number,

  /**
   * Stream Size (8 bytes): This 64-bit integer field contains the size of the user-defined data if this is
   * a stream object. For a root storage object, this field contains the size of the mini stream. For a
   * storage object, this field MUST be set to all zeroes.
   */
  streamSize: bigint
}