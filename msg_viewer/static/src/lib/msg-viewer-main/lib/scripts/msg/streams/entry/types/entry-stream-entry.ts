export interface EntryStreamData {
  /**
   * Name Identifier/String Offset (4 bytes): If this property is a numerical named property (as specified by the Property Kind subfield of the Index and Kind Information field), this value is the LID part of the PropertyName structure, as specified in [MS-OXCDATA] section 2.6.1. If this property is a string named property, this value is the offset in bytes into the strings stream where the value of the Name field of the PropertyName structure is located.
   */
  nameIdOrStringOffset: number,

  /**
   * Property Index (2 bytes): Sequentially increasing, zero-based index. This MUST be 0 for the first named property, 1 for the second, and so on.
   */
  propertyIndex: number,

  /**
   * GUID Index (15 bits): Index into the GUID stream. The possible values are shown in the following table.
   */
  guidIndex: number,

  /**
   * Property Kind (1 bit): Bit indicating the type of the property; zero (0) if numerical named property and 1 if string named property.
   */
  propertyKind: PropertyKind
}

export enum PropertyKind {
  NUMERICAL = 0,
  STRING = 1
}