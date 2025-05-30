import type { CompoundFile } from "../../compound-file/compound-file";
import { NAME_ID_FOLDER_NAME } from "../constants/folders";
import type { EntryStreamData } from "./types/entry-stream-entry";

const DATA_SIZE = 8;
const STREAM_NAME = "__substg1.0_00030102";

export function getEntryStreamData(file: CompoundFile): EntryStreamData[] | null {
  const folder = file.directory.get(NAME_ID_FOLDER_NAME, file.directory.entries[0].childId, false);
  if (!folder) return null;

  const entry = file.directory.get(STREAM_NAME, folder.childId, false);
  if (!entry) return null;

  const list: EntryStreamData[] = [];
  file.readStream(entry,
    (offset, bytes) => {
      const data = getData(file.view, offset);
      list.push(data);
    },
    DATA_SIZE,
  );

  return list;
}

function getData(view: DataView, offset: number): EntryStreamData {
  const nameIdOrStringOffset = view.getUint32(offset, true);
  offset += 4;

  const guidWithKind = view.getUint16(offset, true);
  const propertyKind = guidWithKind & 1;
  const guidIndex = guidWithKind >> 1;
  offset += 2;

  const propertyIndex = view.getUint16(offset, true)
  offset += 2;  

  return {
    nameIdOrStringOffset,
    guidIndex,
    propertyIndex,
    propertyKind
  }
}