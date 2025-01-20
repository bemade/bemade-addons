import type { Header } from "./header";
import { sectorOffset } from "./util";

/**
 * Returns an array of FAT Sector Locations which specify the FAT sector number.
 * DIFAT is used to find all FAT sectors.
 */
export function getDifat(view: DataView, header: Header): number[] {
  // - If Header Major Version is 3, there MUST be 127 fields specified to fill a 512-byte sector minus the "Next DIFAT Sector Location" field.
  // - If Header Major Version is 4, there MUST be 1,023 fields specified to fill a 4,096-byte sector minus the "Next DIFAT Sector Location" field. 
  const fatNumber = header.majorVersion == 3 ? 127 : 1023;
  
  const difat = Array.from(header.difat);

  // Next DIFAT Sector Location (4 bytes): This field specifies the next sector number in the DIFAT chain of sectors. The first DIFAT sector is specified in the Header. The last DIFAT sector MUST set this field to ENDOFCHAIN (0xFFFFFFFE).
  let sector = header.firstDifatSectorLocation;
  while (sector < 0xFFFFFFFE) {
    let offset = sectorOffset(sector, header.sectorSize);
    
    for (let i = 0; i < fatNumber; i++) {
      if (view.getUint32(offset, true) == 0xFFFFFFFF) {
        offset += (fatNumber - i) * 4;
        break;
      }

      difat.push(view.getUint32(offset, true));
      offset += 4;
    }

    sector = view.getUint32(offset, true);
  }

  return difat;
}