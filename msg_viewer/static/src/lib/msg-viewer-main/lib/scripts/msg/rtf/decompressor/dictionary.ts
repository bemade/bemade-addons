const STR = "{\\rtf1\\ansi\\mac\\deff0\\deftab720{\\fonttbl;}{\\f0\\fnil \\froman \\fswiss \\fmodern \\fscript \\fdecor MS Sans SerifSymbolArialTimes New RomanCourier{\\colortbl\\red0\\green0\\blue0\r\n\\par \\pard\\plain\\f0\\fs20\\b\\i\\u\\tab\\tx";

let dict: Uint8Array | null = null;

export function getDictionary(): Uint8Array {
  if (!dict) {
    dict = new Uint8Array(4096);
    for (let i = 0; i < STR.length; i++) {
      dict[i] = STR.charCodeAt(i);
    }
  }
  
  return dict;
}