export interface PropertyHeader {
  /**
   * Custom property used for definying the header size. Can differ based on the reserved bytes
   */
  size: number

  /**
   * Next Recipient ID (4 bytes): The ID to use for naming the next Recipient object storage if one is created inside the .msg file. The naming convention to be used is specified in section 2.2.1. If no Recipient object storages are contained in the .msg file, this field MUST be set to 0.
   */ 
  nextRecipientId?: number,

  /**
   * Next Attachment ID (4 bytes): The ID to use for naming the next Attachment object storage if one is created inside the .msg file. The naming convention to be used is specified in section 2.2.2. If no Attachment object storages are contained in the .msg file, this field MUST be set to 0.
   */ 
  nextAttachmentId?: number,
  
  /** 
   * Recipient Count (4 bytes): The number of Recipient objects.
   */ 
  recipientCount?: number,
  
  /**
   * Attachment Count (4 bytes): The number of Attachment objects.
   */ 
  attachmentCount?: number,
}
