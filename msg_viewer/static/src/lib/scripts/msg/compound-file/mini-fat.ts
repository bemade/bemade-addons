import type { Header } from "./header";
import { fatSectorSize, sectorOffset } from "./util";

/**
 * The mini FAT is used to allocate space in the mini stream. The mini stream is divided into smaller,
 * equal-length sectors, and the sector size that is used for the mini stream is specified from the
 * Compound File Header (64 bytes).
 */
export function getMiniFat(view: DataView, header: Header, fat: number[]): number[] {   
  const sectorSize = fatSectorSize(header);

  const miniFat = [];
    
  let sector = header.firstMiniFatSectorLocation;
  while (sector < 0xFFFFFFFE) {
    let offset = sectorOffset(sector, header.sectorSize);
    for (let i = 0; i < sectorSize; i++) {
      miniFat.push(view.getUint32(offset, true));
      offset += 4;
    }

    sector = fat[sector];
  }

  return miniFat;
}