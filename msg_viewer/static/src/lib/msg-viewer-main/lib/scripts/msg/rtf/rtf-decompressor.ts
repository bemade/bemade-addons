import { crc } from "./decompressor/crc";
import { getDictionary } from "./decompressor/dictionary";
import { CompType, getHeader, type Header } from "./decompressor/header";

export function decompressRTF(view: DataView): string {
  const header = getHeader(view);
  return getContent(view, header);
}

function getContent(view: DataView, header: Header): string {
  if (header.compType == CompType.Uncompressed) {
    const buffer = new Uint8Array(view.buffer.slice(header.headerSize, header.headerSize + header.rawSize));
    return String.fromCharCode(...buffer);
  }

  const currentCRC = crc(view, header.headerSize);
  if (currentCRC !== header.crc) {
    throw new Error(`CRC mismatch! Expected ${header.crc}, got ${currentCRC}.`);
  }

  const output = [];
  const dictionary = getDictionary();

  let offset = header.headerSize;
  let writeOffset = 207;
  let readOffset = 0;
  let canRun = true;
  while (offset <= header.compSize + 4 && canRun) {
    const control = view.getUint8(offset);
    offset += 1;

    for (let i = 0; i < 8; i++) {
      const bit = (control >>> i) & 1;

      if (bit == 0) {
        const literal = view.getUint8(offset);
        offset += 1;

        dictionary[writeOffset] = literal;
        writeOffset = (writeOffset + 1) % dictionary.length;

        output.push(literal);
      } else {
        const ref = view.getUint16(offset);
        const refOffset = ref >>> 4;
        offset += 2;

        if (refOffset == writeOffset) {
          canRun = false;
          break;
        }

        readOffset = refOffset;
        const refLength = 2 + (ref & 0x0f);
        for (let j = 0; j < refLength; j++) {
          const byte = dictionary[readOffset];
          readOffset = (readOffset + 1) % dictionary.length;
          
          dictionary[writeOffset] = byte;
          writeOffset = (writeOffset + 1) % dictionary.length;

          output.push(byte);
        }
      }
    }
  }

  return String.fromCharCode(...output);
}
