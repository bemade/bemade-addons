import type { PropertyType } from "../property-types";

export interface PropertyData {
  /**
   * Property Type (2 bytes): The type of the property.
   */
  propertyType: PropertyType,

  /**
   * Property Id (2 bytes): The id of the property.
   */
  propertyId: number,

  /**
   * Flags (4 bytes): Flags giving context to the property. 
   * Possible values for this field are given in the following table. 
   * Any bitwise combination of the flags is valid.
   * 
   * |--------------------|-------------|--------------------------------------------------------------------------------------------------|
   * | Flag name          | Value       | Description                                                                                      |
   * |--------------------|-------------|--------------------------------------------------------------------------------------------------|
   * | PROPATTR_MANDATORY | 0x00000001  | If this flag is set for a property, that property MUST NOT be deleted from the .msg file         |
   * |                    |             |  (irrespective of which storage it is contained in) and implementations MUST return an error     |
   * |                    |             |  if any attempt is made to do so. This flag is set in circumstances where the implementation     |
   * |                    |             |  depends on that property always being present in the .msg file once it is written there.        |
   * |--------------------|-------------|------------------------------------------------------------------------------------------------- |
   * | PROPATTR_READABLE  | 0x00000002  | If this flag is not set on a property, that property MUST NOT be read from the .msg file and     |
   * |                    |             |  implementations MUST return an error if any attempt is made to read it. This flag is set on all |
   * |                    |             |  properties unless there is an implementation-specific reason to prevent a property from being   |
   * |                    |             |  read from the .msg file.                                                                        |
   * |--------------------|-------------|--------------------------------------------------------------------------------------------------|
   * | PROPATTR_WRITABLE  | 0x00000004  | If this flag is not set on a property, that property MUST NOT be modified or deleted and         |
   * |                    |             | implementations MUST return an error if any attempt is made to do so. This flag is set in        |
   * |                    |             | circumstances where the implementation depends on the properties being writable.                 |
   * |--------------------|-------------|--------------------------------------------------------------------------------------------------|
   */
  flags: number,

  /**
   * (8 bytes): 
   * - If Fixed Length Property:
   *   Data (variable): The value of the property. The size of this field depends upon the property type, which is specified in the Property Tag field, as specified in section 2.4.2.1. The size required for each property type is specified in [MS-OXCDATA] section 2.11.1.
   *   Reserved (variable): This field MUST be ignored when reading a .msg file. The size of the Reserved field is the difference between 8 bytes and the size of the Data field; if the size of the Reserved field is greater than 0, this field MUST be set to 0 when writing a .msg file.
   * - If Variable Length Property:
   *   Size (4 bytes): This value is interpreted based on the property type, which is specified in the Property Tag field. If the message contains an embedded message attachment or a storage attachment, this field MUST be set to 0xFFFFFFFF. Otherwise, the following table shows how this field is interpreted for each property type. The property types are specified in [MS-OXCDATA] section 2.11.1.
   *   Reserved (4 bytes): This field MUST be ignored when reading a .msg file. 
   */
  valueOrSize: number | bigint,
}