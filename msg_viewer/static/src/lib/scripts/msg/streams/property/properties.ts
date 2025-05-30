import { PtypBinary, PtypObject, PtypString, PtypTime, type PropertyType } from "./property-types";

export const enum PropertySource { 
  Stream, // Property can be found in a dedicated stream
  Property // Property is located in property stream
}

export const ROOT_PROPERTIES: Property[] = [
  { id: "0E06", name:"date", type: PtypTime, source: PropertySource.Property },
  { id: "0037", name:"subject", type: PtypString, source: PropertySource.Stream },
  { id: "0c1a", name:"senderName", type: PtypString, source: PropertySource.Stream },
  { id: "5d02", name:"senderEmail", type: PtypString, source: PropertySource.Stream },
  { id: "1000", name:"body", type: PtypString, source: PropertySource.Stream },
  { id: "1013", name:"bodyHTML", type: PtypString, source: PropertySource.Stream },
  { id: "1009", name:"bodyRTF", type: PtypBinary, source: PropertySource.Stream },
  { id: "007d", name:"headers", type: PtypString, source: PropertySource.Stream },
  { id: "0E04", name:"toRecipients", type: PtypString, source: PropertySource.Stream },
  { id: "0E03", name:"ccRecipients", type: PtypString, source: PropertySource.Stream },
];

export const ATTACH_PROPERTIES: Property[]= [
  { id: "3703", name:"extension", type: PtypString, source: PropertySource.Stream },
  { id: "3707", name:"fileName", type: PtypString, source: PropertySource.Stream },
  { id: "370e", name:"mimeType", type: PtypString, source: PropertySource.Stream },
  { id: "3A0C", name:"language", type: PtypString, source: PropertySource.Stream },
  { id: "3001", name:"displayName", type: PtypString, source: PropertySource.Stream },
  { id: "3701", name:"content", type: PtypBinary, source: PropertySource.Stream },
  { id: "3701", name:"embeddedMsgObj", type: PtypObject, source: PropertySource.Stream },
];

export const RECIP_PROPERTIES: Property[] = [
  { id: "3001", name:"name", type: PtypString, source: PropertySource.Stream },
  { id: "39fe", name:"email", type: PtypString, source: PropertySource.Stream },
];

export interface Property {
  id: string,
  name: string,
  type: PropertyType,
  source: PropertySource,
}
