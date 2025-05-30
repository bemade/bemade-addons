import type { CompoundFile } from "../../compound-file/compound-file";
import type { DirectoryEntry } from "../../compound-file/directory/types/directory-entry";
import { PROPERTY_TYPES } from "./property-types";
import type { PropertyHeader } from "./types/property-header";
import type { PropertyData } from "./types/property-data";
import type { PropertyStreamEntry } from "./types/property-stream-entry";

const STREAM_NAME = "__properties_version1.0";
const DATA_SIZE = 16;

export function getPropertyStreamEntry(file: CompoundFile, folder: DirectoryEntry): PropertyStreamEntry | null {
  const entry = file.directory.get(STREAM_NAME, folder.childId, false);
  if (!entry) return null;

  let header;
  const data = new Map();
  file.readStream(entry,
    (offset) => {
      const property = getProperty(file.view, offset);
      data.set(property.propertyId.toString(16).toLowerCase().padStart(4, "0"), property);
    },
    DATA_SIZE,
    (offset) => {
      header = getHeader(file.view, offset, folder.entryName);
      return header.size;
    }
  );

  return { header: header!, data: data };
}

function getProperty(view: DataView, offset: number): PropertyData {
  const propertyTag = view.getUint32(offset, true);
  const propertyType = PROPERTY_TYPES[0xFFFF & propertyTag];
  const propertyId = propertyTag >>> 16;

  offset += 4;
  
  const flags = view.getUint32(offset, true);
  offset += 4;
  
  const valueOrSize = (!propertyType?.size || propertyType?.multi)
    ? view.getUint32(offset, true)
    : (propertyType.size == 1) 
      ? view.getUint8(offset)
      : propertyType.size == 2
        ? view.getUint16(offset, true)
        : propertyType.size == 4
          ? view.getUint32(offset, true)
          : view.getBigUint64(offset, true);

  return {
    propertyType,
    propertyId,
    flags,  
    valueOrSize
  };
}

function getHeader(view: DataView, offset: number, folderName: string): PropertyHeader {
  if (["__attach", "__recip"].some(v => folderName.startsWith(v))) return { size: 8 };

  const initialOffset = offset;

  // Reserved (8 bytes): This field MUST be set to zero when writing a .msg file and MUST be ignored when reading a .msg file.
  offset += 8;

  const nextRecipientId = view.getUint32(offset, true);
  offset += 4;

  const nextAttachmentId = view.getUint32(offset, true);
  offset += 4;

  const recipientCount = view.getUint32(offset, true);
  offset += 4;

  const attachmentCount = view.getUint32(offset, true);
  offset += 4;
  
  if (folderName.startsWith("Root")) {
    // Reserved (8 bytes): This field MUST be set to 0 when writing a .msg file and MUST be ignored when reading a .msg file.
    offset += 8;
  }
  

  return { size: offset - initialOffset, nextRecipientId, nextAttachmentId, recipientCount, attachmentCount };
}

