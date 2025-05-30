declare module "*.html" {
  const content: string;
  export default content;
}

interface Window {
  gtag: (event: string, type: string, args: { [key: string]: any }) => void;
}