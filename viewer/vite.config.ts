import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: { port: 5173 },
  // GitHub Pages 배포 시 아래 주석 해제 후 저장소 이름으로 변경
  // base: '/semantic-graph-viewer/',
})
