import { ColorFlag } from "./enums/color-flag";
import type { DirectoryEntry } from "./types/directory-entry";
import { ObjectType } from "./enums/object-type";
import type { Header } from "../header";
import { sectorOffset } from "../util";
import { TEXT_DECODER } from "../constants/text-decoder";

export class Directory {
  constructor(
    public readonly entries: DirectoryEntry[], 
    public readonly miniStreamLocations: number[]
  ) {}

  static getDirectory(view: DataView, header: Header, fat: number[]): Directory {
    const entrySize = 128;
    const entriesCount = header.sectorSize / entrySize;
  
    const entries: DirectoryEntry[] = [];
  
    let sector = header.firstDirSectorLocation;
    while (sector < 0xFFFFFFFE) {
      let offset = sectorOffset(sector, header.sectorSize);
  
      for (let i = 0; i < entriesCount; i++) {
        entries.push(this.directoryEntry(view, offset));
        
        offset += entrySize;
      }
  
      sector = fat[sector];
    }
  
    return new Directory(
      entries,
      this.getMiniStreamLocations(entries[0].startingSectorLocation, fat),
    );
  }

  /** 
   * Traverses a Red-Black Tree to find the entry with the given name. 
   */
  get(name: string, root: number, deep: boolean): DirectoryEntry | null {
    if (root < 0 || root >= this.entries.length) return null;

    const entry = this.entries[root];
    if (!entry) return null;

    const diff = this.compareName(name, entry.entryName);

    if (diff < 0) {
      const left = this.get(name, entry.leftSiblingId, deep);
      if (left) return left;
    }else if (diff > 0) {
      const right = this.get(name, entry.rightSiblingId, deep);
      if (right) return right;
    } else {
      return entry;
    }

    return deep ? this.get(name, entry.childId, deep) : null;
  }

  private static getMiniStreamLocations(sector: number, fat: number[]): number[] {
    const locations: number[] = [];
  
    while(sector < 0xFFFFFFFE) {
      locations.push(sector);
      sector = fat[sector];
    }
  
    return locations;
  }
  
  private static directoryEntry(view: DataView, offset: number): DirectoryEntry {
    const entryNameLength = view.getUint16(offset + 64, true);
    const entryName = entryNameLength > 0 
      ? TEXT_DECODER.decode(new DataView(view.buffer, offset, entryNameLength - 2))
      : "";
    offset += 66;
  
    const objectType = view.getUint8(offset) as ObjectType;
    offset += 1;
  
    const colorFlag = view.getUint8(offset) as ColorFlag;
    offset += 1;
  
    const leftSiblingId = view.getUint32(offset, true);
    offset += 4;
  
    const rightSiblingId = view.getUint32(offset, true);
    offset += 4;
  
    const childId = view.getUint32(offset, true);
    offset += 4;
    
    const clsid = "";
    offset += 16;
  
    const stateBits = view.getUint32(offset, true);
    offset += 4;
  
    const creationTime = view.getBigUint64(offset, true);
    offset += 8;
  
    const modifiedTime = view.getBigUint64(offset, true);
    offset += 8;
  
    const startingSectorLocation = view.getUint32(offset, true);
    offset += 4;
  
    const streamSize = view.getBigUint64(offset, true);
    offset += 8;
  
    return {
      entryName,
      entryNameLength,
      objectType,
      colorFlag,
      leftSiblingId,
      rightSiblingId,
      childId,
      clsid,
      stateBits,
      creationTime,
      modifiedTime,
      startingSectorLocation,
      streamSize
    }
  }
  
  print() {
    this.traverse((entry, depth) => console.log("\t".repeat(depth), entry.entryName));
  }

  traverse(action: (entry: DirectoryEntry, depth: number) => void) {
    this.traverseFromRoot(0, 0, action);
  }

  private traverseFromRoot(root: number, depth: number, action: (entry: DirectoryEntry, depth: number) => void) {
    if (root < 0 || root >= this.entries.length) return;

    const entry = this.entries[root];
    if (!entry) return;

    this.traverseFromRoot(entry.leftSiblingId, depth, action);
    this.traverseFromRoot(entry.rightSiblingId, depth, action);
    
    action(entry, depth);
    this.traverseFromRoot(entry.childId, depth + 1, action);
  }

  private compareName(name1: string, name2: string) {
    if (name1.length < name2.length) return -1;
    if (name1.length > name2.length) return 1;
    return name1.toUpperCase().localeCompare(name2.toUpperCase());
  }
}