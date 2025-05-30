import type { Header } from "./header";
import { fatSectorSize, sectorOffset } from "./util";

/**
 * The FAT is an array of sector numbers that represent the allocation of space within the file, grouped
 * into FAT sectors. Each stream is represented in the FAT by a sector chain, in much the same fashion 
 * as a FAT file system.
 */
export function getFat(view: DataView, header: Header, difat: number[]): number[] {
  const sectorSize = fatSectorSize(header);

  const fat: number[] = [];
  for (let i = 0; i < difat.length; i++) {
    let offset = sectorOffset(difat[i], header.sectorSize);
    
    for (let j = 0; j < sectorSize; j++) {
      const nextSector = view.getUint32(offset, true);
      fat.push(nextSector);
      offset += 4;
    }
  }

  return fat;
}