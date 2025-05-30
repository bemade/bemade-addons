export interface Header {
  // Header Signature (8 bytes): Identification signature for the compound file structure, and MUST be set to the value 0xD0, 0xCF, 0x11, 0xE0, 0xA1, 0xB1, 0x1A, 0xE1.
  signature: number[], 

  // Minor Version (2 bytes): Version number for nonbreaking changes. This field SHOULD be set to 0x003E if the major version field is either 0x0003 or 0x0004.
  minorVersion: number,

  // Major Version (2 bytes): Version number for breaking changes. This field MUST be set to either 0x0003 (version 3) or 0x0004 (version 4).
  majorVersion: number,

  // Byte Order (2 bytes): This field MUST be set to 0xFFFE. This field is a byte order mark for all integer fields, specifying little-endian byte order.
  byteOrder: number,

  // Sector Shift (2 bytes): This field MUST be set to 0x0009, or 0x000c, depending on the Major Version field.
  // Sector Size = 2 ^ SectorShift. e.g. 2 ^ 9 = 512, 2 ^ 12 = 4096
  sectorSize: number,

  // Mini Sector Shift (2 bytes): This field MUST be set to 0x0006. This field specifies the sector size of the Mini Stream as a power of 2. The sector size of the Mini Stream MUST be 64 bytes.
  // Mini Sector Size = 2 ^ Mini Sector Shift. e.g. 2 ^ 6 = 64
  miniSectorSize: number,

  // Number of Directory Sectors (4 bytes): This integer field contains the count of the number of directory sectors in the compound file.
  numberOfDirectorySectors: number,

  // Number of FAT Sectors (4 bytes): This integer field contains the count of the number of FAT sectors in the compound file.
  numberOfFatSectors: number, 

  // First Directory Sector Location (4 bytes): This integer field contains the starting sector number for the directory stream.
  firstDirSectorLocation: number, 
  
  // Transaction Signature Number (4 bytes): This integer field MAY contain a sequence number that is incremented every time the compound file is saved by an implementation that supports file transactions. This is the field that MUST be set to all zeroes if file transactions are not implemented.
  transactionSignatureNumber: number, 
  
  // Mini Stream Cutoff Size (4 bytes): This integer field MUST be set to 0x00001000. This field specifies the maximum size of a user-defined data stream that is allocated from the mini FAT and mini stream, and that cutoff is 4,096 bytes. Any user-defined data stream that is greater than or equal to this cutoff size must be allocated as normal sectors from the FAT.
  miniStreamCutOffSize: number, 
  
  // First Mini FAT Sector Location (4 bytes): This integer field contains the starting sector number for the mini FAT.
  firstMiniFatSectorLocation: number, 
  
  // Number of Mini FAT Sectors (4 bytes): This integer field contains the count of the number of mini FAT sectors in the compound file.
  numberOfMiniFatSectors: number,
  
  // First DIFAT Sector Location (4 bytes): This integer field contains the starting sector number for the DIFAT.
  firstDifatSectorLocation: number, 
  
  // Number of DIFAT Sectors (4 bytes): This integer field contains the count of the number of DIFAT sectors in the compound file.
  numberOfDifatSectors: number,

  // DIFAT (436 bytes): This array of 32-bit integer fields contains the first 109 FAT sector locations of the compound file. For version 4 compound files, the header size (512 bytes) is less than the sector size (4,096 bytes), so the remaining part of the header (3,584 bytes) MUST be filled with all zeroes.
  // The DIFAT array is used to represent storage of the FAT sectors. 
  difat: number[]
}

export function getHeader(view: DataView): Header {
  const signature = [0xD0, 0xCF, 0x11, 0xE0, 0xA1, 0xB1, 0x1A, 0xE1];
  for (var offset = 0; offset < 8; offset++) {
    if (view.getUint8(offset) != signature[offset]) {
      throw new Error("Signature mismatch!"); 
    }
  }

  // Header CLSID (16 bytes): Reserved and unused class ID that MUST be set to all zeroes 
  offset += 16;

  const minorVersion = view.getUint16(offset, true);
  offset += 2;

  const majorVersion = view.getUint16(offset, true);
  offset += 2;

  const byteOrder = view.getUint16(offset, true);
  offset += 2;

  const sectorSize = Math.pow(2, view.getUint16(offset, true));
  offset += 2;

  const miniSectorSize = Math.pow(2, view.getUint16(offset, true));
  offset += 2;

  // Reserved (6 bytes): This field MUST be set to all zeroes. 
  offset += 6;
  
  const numberOfDirectorySectors = view.getUint32(offset, true)
  offset += 4;

  const numberOfFatSectors = view.getUint32(offset, true)
  offset += 4;

  const firstDirSectorLocation = view.getUint32(offset, true);
  offset += 4;

  const transactionSignatureNumber = view.getUint32(offset, true);
  offset += 4;
  
  const miniStreamCutOffSize = view.getUint32(offset, true);
  offset += 4;

  const firstMiniFatSectorLocation = view.getUint32(offset, true);
  offset += 4;

  const numberOfMiniFatSectors = view.getUint32(offset, true)
  offset += 4;
  
  const firstDifatSectorLocation = view.getUint32(offset, true)
  offset += 4;
    
  const numberOfDifatSectors = view.getUint32(offset, true);
  offset += 4;

  const difat: number[] = [];
  for (let i = 0; i < 436; i += 4) {
    const fat = view.getUint32(offset, true);
    if (fat == 0xFFFFFFFF) break;
    
    difat.push(fat);
    offset += 4;
  }

  return {
    signature, byteOrder, sectorSize, miniSectorSize, minorVersion, majorVersion, numberOfDirectorySectors, 
    numberOfFatSectors, firstDirSectorLocation, transactionSignatureNumber, 
    miniStreamCutOffSize, firstMiniFatSectorLocation, numberOfMiniFatSectors,
    firstDifatSectorLocation, numberOfDifatSectors, difat
  }
}
