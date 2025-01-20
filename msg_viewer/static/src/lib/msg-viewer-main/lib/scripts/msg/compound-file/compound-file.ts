import { getDifat } from "./difat";
import { Directory } from "./directory/directory";
import type { DirectoryEntry } from "./directory/types/directory-entry";
import { getFat } from "./fat";
import { getHeader, type Header } from "./header";
import { getMiniFat } from "./mini-fat";
import { streamSectorOffset } from "./util";

export class CompoundFile {
  constructor(
    public readonly view: DataView, 
    public readonly header: Header,
    public readonly difat: number[],
    public readonly fat: number[],
    public readonly miniFat: number[],
    public readonly directory: Directory,
  ) {}
  
  static create(view: DataView) {
    const header = getHeader(view);
    const difat = getDifat(view, header);
    const fat = getFat(view, header, difat);
    const miniFat = getMiniFat(view, header, fat);
    const directory = Directory.getDirectory(view, header, fat);

    return new CompoundFile(view, header, difat, fat, miniFat, directory);
  }

  readStream(
    entry: DirectoryEntry,
    getDataAction: (offset: number, bytesToRead: number) => void,
    entrySize?: number,
    getHeaderAction?: (offset: number) => number
  ) {
    let sector = entry.startingSectorLocation;
    if (sector >= 0xFFFFFFFE) return;

    let sectorSize = this.header.sectorSize;
    let fat = this.fat;
    
    if (entry.streamSize < this.header.miniStreamCutOffSize) {
      sectorSize = this.header.miniSectorSize;
      fat = this.miniFat;
    }
  
    let offset = streamSectorOffset(sector, this.header, entry.streamSize, this.directory.miniStreamLocations);
    let initialOffset = offset;

    const headerSize = getHeaderAction ? getHeaderAction(offset) : 0;
    let streamSize = entry.streamSize - BigInt(headerSize);
    offset += headerSize;
    entrySize = entrySize ?? Math.min(Number(streamSize), this.header.miniSectorSize);

    while(streamSize > 0) {
      if (offset - initialOffset >= sectorSize) {
        sector = fat[sector];
        if (sector >= 0xFFFFFFFE) break;
  
        offset = streamSectorOffset(sector, this.header, entry.streamSize, this.directory.miniStreamLocations);
        initialOffset = offset;
      }
  
      let bytes = Math.min(entrySize, Number(streamSize));
      getDataAction(offset, bytes);

      streamSize -= BigInt(bytes);
      offset += bytes;
    }
  }

  toString(): string {
    const obj = { 
      header: this.header, 
      difat: this.difat, 
      fat: this.fat, 
      miniFat: 
      this.miniFat, 
      directory: 
      this.directory 
    };
    
    return JSON.stringify(obj, (_, v) => typeof v === 'bigint' ? v.toString() : v, "\t");
  }
}