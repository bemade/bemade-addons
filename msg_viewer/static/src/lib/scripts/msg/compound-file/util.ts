import type { Header } from "./header";

/**
 * Based on a non-stream sector number returns the byte offset in the Buffer.
 */
export function sectorOffset(sector: number, sectorSize: number): number {
  return (sector + 1) * sectorSize;
}

/**
 * Based on a stream sector number returns the byte offset in the Buffer.
 */
export function streamSectorOffset(sector: number, header: Header, streamSize: bigint, miniStreamLocations: number[]): number {
  let offset = sectorOffset(sector, header.sectorSize);
  
  // Calculates the offset in ministream if streamSize is smaller than miniStreamCutOffSize
  if (streamSize < header.miniStreamCutOffSize) {
    offset = sector * header.miniSectorSize;
    const miniStreamSector = Math.floor(offset / header.sectorSize);
    const miniStreamOffset = offset % header.sectorSize;
    offset = sectorOffset(miniStreamLocations[miniStreamSector], header.sectorSize) + miniStreamOffset ;
  }

  return offset;
}

export function fatSectorSize(header: Header) {
  // If Header Major Version is 3, there MUST be 128 fields specified to fill a 512-byte sector.
  // If Header Major Version is 4, there MUST be 1,024 fields specified to fill a 4,096-byte sector.
  return header.majorVersion == 3 ? 128 : 1024;
}
