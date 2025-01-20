// Import the required modules
import { MsgParser } from './scripts/msg/msg-parser';
import { HtmlTemplateUtil } from './scripts/utils/html-template-util';

// Function to load and display the MSG file
async function loadMsgFile(url) {
    try {
        // Fetch the MSG file
        const response = await fetch(url);
        const arrayBuffer = await response.arrayBuffer();

        // Parse the MSG file
        const parser = new MsgParser(arrayBuffer);
        const message = await parser.parse();

        // Create HTML from the message
        const html = HtmlTemplateUtil.createMessageHtml(message);
        
        // Display the message
        document.body.innerHTML = html;
    } catch (error) {
        console.error('Error loading MSG file:', error);
        document.body.innerHTML = `<div class="error">Error loading MSG file: ${error.message}</div>`;
    }
}

// Get the file URL from the query parameters
const urlParams = new URLSearchParams(window.location.search);
const fileUrl = urlParams.get('file');

// Load the MSG file if a URL is provided
if (fileUrl) {
    loadMsgFile(fileUrl);
} else {
    document.body.innerHTML = '<div class="error">No MSG file URL provided</div>';
}
