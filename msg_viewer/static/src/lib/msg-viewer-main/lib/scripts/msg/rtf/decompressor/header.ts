export function getHeader(view: DataView): Header {
  let offset = 0;
  
  const compSize = view.getUint32(offset, true);
  offset += 4;

  const rawSize = view.getUint32(offset, true);
  offset += 4;
  
  const compType = view.getUint32(offset, true) === 0x75465A4C ? CompType.Compressed : CompType.Uncompressed;
  offset += 4;  
  
  const crc = view.getUint32(offset, true);
  offset += 4;  

  return { compSize, rawSize, compType, crc, headerSize: offset };
}

export interface Header {
  /**
   * Writers MUST set the COMPSIZE field to the length of the compressed data
   * (the CONTENTS field) in bytes plus 12 (the count of the remaining bytes from the header). 
   */
  compSize: number;

  /**
   * The size in bytes of the uncompressed content.
   */
  rawSize: number;

  /**
   * The type of compression.
   */
  compType: CompType;

  /**
   * Cyclic redundancy check. Used to verify that the file is not broken.
   * If the COMPTYPE field is set to COMPRESSED, then the CRC field is computed from the CONTENTS field. 
   * If the COMPTYPE field is set to UNCOMPRESSED, then the CRC field MUST be set to %x00.00.00.00.
   */
  crc: number;

  /**
   * The size in bytes of the header.
   */
  headerSize: number;
}

export const enum CompType { Compressed, Uncompressed }