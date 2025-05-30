const SIZE = 1000;
const UNITS = ['bytes', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB'];
   
export function bytesWithUnits(bytes: number): string {
  let unit = 0;
  while(bytes >= SIZE){
    bytes = bytes / SIZE;
    unit++;
  }
  
  return `${bytes.toFixed(bytes < 10 && unit > 0 ? 1 : 0)} ${UNITS[unit]}`;
}
