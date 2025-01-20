import { CompoundFile } from "./compound-file/compound-file";
import { TEXT_DECODER } from "./compound-file/constants/text-decoder";
import type { DirectoryEntry } from "./compound-file/directory/types/directory-entry";
import { ATTACH_PROPERTIES, PropertySource, RECIP_PROPERTIES, ROOT_PROPERTIES, type Property } from "./streams/property/properties";
import { getPropertyStreamEntry } from "./streams/property/property-stream";
import { PtypBinary, PtypObject, PtypString, PtypTime, type PropertyType } from "./streams/property/property-types";
import type { PropertyStreamEntry } from "./streams/property/types/property-stream-entry";
import type { Attachment, Message, MessageContent, Recipient } from "./types/message";

export function parse(view: DataView): Message {
  const file = CompoundFile.create(view);
  const dir = file.directory.entries[0];

  return parseDir(file, dir);
}

export function parseDir(file: CompoundFile, dir: DirectoryEntry): Message {
  const pStreamEntry = getPropertyStreamEntry(file, dir)!;

  return { 
    file: file,
    content: getContent(file, dir, pStreamEntry), 
    attachments: getAttachments(file, dir),
    recipients: getRecipients(file, dir),
  };
}

function getContent(file: CompoundFile, dir: DirectoryEntry, pStreamEntry: PropertyStreamEntry): MessageContent {
  return getValue(file, ROOT_PROPERTIES, dir, pStreamEntry);
}

function getRecipients(file: CompoundFile, dir: DirectoryEntry): Recipient[] {
  return getValues(file, dir, RECIP_PROPERTIES, "recip");
}

function getAttachments(file: CompoundFile, dir: DirectoryEntry): Attachment[] {
  return getValues(file, dir, ATTACH_PROPERTIES, "attach");
}

function getValues<T>(file: CompoundFile, dir: DirectoryEntry, properties: Property[], prefix: string): T[] {
  const list: T[] = [];

  for (let i = 0; i < 2048; i++) {
    const directory = file.directory.get(`__${prefix}_version1.0_#${i.toString(16).padStart(8, "0")}`, dir.childId, false);
    if (!directory) break;

    const pStreamEntry = getPropertyStreamEntry(file, directory)!;
    list.push(getValue(file, properties, directory, pStreamEntry));
  }

  return list;
}

function getValue<T>(file: CompoundFile, properties: Property[], dir: DirectoryEntry, entry: PropertyStreamEntry): T {
  return properties.reduce((acc, p) => {
    if (p.source == PropertySource.Stream) {
      const streamName = `__substg1.0_${p.id.padStart(4, "0")}${p.type.id.toString(16).padStart(4, "0")}`;
      const entry = file.directory.get(streamName, dir.childId, false);
      if (!entry) return acc;
      acc[p.name as keyof T] = getValueFromStream(file, entry, p.type) as T[keyof T];
    } else {
      const value = getValueFromProperty(entry, p);
      if (!value) return acc;
      acc[p.name as keyof T] = value as T[keyof T];
    }
    
    return acc;
  }, {} as T);
}

function getValueFromProperty(entry: PropertyStreamEntry, property: Property) {
  const value = entry.data.get(property.id.toLowerCase())?.valueOrSize;
  if (!value) return "";
  
  switch (property.type) {
    case PtypTime: {
      // Subtracting the number of seconds between January 1, 1601 and January 1, 1970.
      return new Date(Number(value as bigint / 10000n) - 1.16444736e13);
    }
    default: return value;
  }  
}

function getValueFromStream(file: CompoundFile, entry: DirectoryEntry, type: PropertyType)  {
  switch (type) {
    case PtypString: {
      let value = "";
      file.readStream(entry, (offset, bytes) => {
        value += TEXT_DECODER.decode(new DataView(file.view.buffer, offset, bytes));
      });

      return value;
    };
    case PtypBinary: {
      const chunks = new Uint8Array(Number(entry.streamSize));
      let pos = 0;
      file.readStream(entry, (offset, bytes) => {
        const chunk = file.view.buffer.slice(offset, offset + bytes);
        chunks.set(new Uint8Array(chunk), pos);
        pos += bytes;
      });

      return new DataView(chunks.buffer);
    };
    case PtypObject: {
      return entry;
    }
    default: return null;
  };
}
