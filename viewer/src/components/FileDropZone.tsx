// Design Ref: §5.2 — FileDropZone: 파일 선택 버튼 + 드래그앤드롭 처리
import { useRef, useState, DragEvent } from 'react'
import './FileDropZone.css'

interface FileDropZoneProps {
  onLoad: (file: File) => void;
  error: string | null;
}

export function FileDropZone({ onLoad, error }: FileDropZoneProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [isDragging, setIsDragging] = useState(false)

  const handleDragOver = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setIsDragging(true)
  }

  const handleDragLeave = (e: DragEvent<HTMLDivElement>) => {
    // 자식 요소로 이동 시 이벤트 무시
    if (e.currentTarget.contains(e.relatedTarget as Node)) return
    setIsDragging(false)
  }

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setIsDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) onLoad(file)
  }

  const handleFileChange = () => {
    const file = inputRef.current?.files?.[0]
    if (file) onLoad(file)
    // 같은 파일 재선택 가능하도록 초기화
    if (inputRef.current) inputRef.current.value = ''
  }

  return (
    <div className="fdz-root">
      <div
        className={`fdz-zone${isDragging ? ' fdz-zone--dragging' : ''}`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        <svg className="fdz-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
          <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m6.75 12l-3-3m0 0l-3 3m3-3v6m-1.5-15H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
        </svg>

        <p className="fdz-main-text">
          graph.json을 드래그하거나
        </p>

        <button
          className="fdz-button"
          onClick={() => inputRef.current?.click()}
          type="button"
        >
          파일 선택
        </button>

        <input
          ref={inputRef}
          type="file"
          accept=".json"
          style={{ display: 'none' }}
          onChange={handleFileChange}
        />

        <div className="fdz-hint">
          <p className="fdz-hint-title">── Analyzer 산출물 위치 ──</p>
          <p className="fdz-hint-path">&#123;source_path&#125;/_ai_analysis/graph.json</p>
        </div>

        {error && <p className="fdz-error">{error}</p>}
      </div>
    </div>
  )
}
