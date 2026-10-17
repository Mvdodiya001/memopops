/// <reference types="vite/client" />

declare module "*.json" {
  const value: unknown
  export default value
}

declare module "*?raw" {
  const value: string
  export default value
}

interface ImportMetaEnv {
  readonly VITE_API_BASE?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
