import { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import Icon from './Icon.jsx'

export default function SidePanel({ messages = [], onSend, sending = false }) {
  const [tab, setTab] = useState('chat')

  // Extraer archivos y codigo de los mensajes para las tabs
  const files = messages.filter(m => m.file).map(m => ({
    name: m.file,
    time: m.time,
    from: m.who === 'jarvis' ? 'Jarvis' : 'Usted',
  }))
  const codeSnippets = messages.filter(m => m.code).map(m => ({
    code: m.code,
    time: m.time,
    context: m.body || '',
  }))

  return (
    <aside className="h-full bg-bg-1 border-l border-border flex flex-col overflow-hidden">
      <div className="flex p-1.5 gap-0.5 border-b border-border">
        {['chat', 'archivos', 'codigo'].map(t => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            className={
              'flex-1 py-1.5 px-2.5 text-[12px] font-medium rounded-md transition capitalize ' +
              (tab === t
                ? 'bg-bg-3 text-fg-1'
                : 'text-fg-3 hover:bg-bg-2 hover:text-fg-2')
            }
          >
            {t === 'codigo' ? 'Código' : t === 'archivos' ? 'Archivos' : 'Chat'}
            {t === 'archivos' && files.length > 0 && (
              <span className="ml-1.5 text-[10px] text-fg-4 bg-bg-2 px-1.5 py-0.5 rounded-full">{files.length}</span>
            )}
            {t === 'codigo' && codeSnippets.length > 0 && (
              <span className="ml-1.5 text-[10px] text-fg-4 bg-bg-2 px-1.5 py-0.5 rounded-full">{codeSnippets.length}</span>
            )}
          </button>
        ))}
      </div>

      {tab === 'chat' && <ChatTab messages={messages} onSend={onSend} sending={sending} />}
      {tab === 'archivos' && <FilesTab files={files} />}
      {tab === 'codigo' && <CodeTab snippets={codeSnippets} />}
    </aside>
  )
}

/* ================================================================
   TAB: Chat
   ================================================================ */
function ChatTab({ messages, onSend, sending }) {
  const [draft, setDraft] = useState('')
  const scrollRef = useRef(null)
  const textareaRef = useRef(null)

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight
  }, [messages])

  const submit = () => {
    const t = draft.trim()
    if (!t || sending) return
    onSend?.(t)
    setDraft('')
    if (textareaRef.current) textareaRef.current.style.height = 'auto'
  }

  return (
    <>
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 flex flex-col gap-5">
        {messages.length === 0 && (
          <div className="m-auto text-center text-fg-4 text-[12px] px-6">
            Ningún mensaje aún. Escriba algo o diga <span className="text-fg-2">"Jarvis"</span>.
          </div>
        )}
        <AnimatePresence initial={false}>
          {messages.map(m => (
            <motion.div
              key={m.id}
              layout
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.22, ease: 'easeOut' }}
              className={'flex ' + (m.who === 'user' ? 'justify-end' : 'justify-start')}
            >
              <Message {...m} />
            </motion.div>
          ))}
        </AnimatePresence>
        {sending && <TypingIndicator />}
      </div>

      <div className="p-3 border-t border-border bg-bg-1">
        <div className="flex items-end rounded-lg bg-bg-2 border border-border focus-within:border-[var(--accent)] focus-within:shadow-[0_0_0_3px_var(--accent-muted)] transition">
          <textarea
            ref={textareaRef}
            value={draft}
            onChange={(e) => {
              setDraft(e.target.value)
              e.target.style.height = 'auto'
              e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px'
            }}
            onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit() } }}
            placeholder={sending ? 'Esperando respuesta...' : 'Escriba o diga "Jarvis"...'}
            disabled={sending}
            rows={1}
            className="flex-1 bg-transparent border-0 outline-none text-fg-1 text-[13px] px-3 py-2.5 leading-[1.45] resize-none min-h-[38px] max-h-[120px] placeholder:text-fg-4 disabled:opacity-60"
          />
          <div className="flex items-center p-1 gap-0.5">
            <SmallBtn title="Adjuntar"><Icon name="paperclip" size={14} /></SmallBtn>
            <SmallBtn title="Imagen"><Icon name="image" size={14} /></SmallBtn>
            <button
              type="button"
              title="Enviar"
              onClick={submit}
              disabled={sending || !draft.trim()}
              className="inline-flex items-center justify-center w-[30px] h-[30px] rounded-md bg-[var(--accent)] text-white hover:brightness-110 transition disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <Icon name="send" size={14} strokeWidth={2} />
            </button>
          </div>
        </div>
      </div>
    </>
  )
}

/* ================================================================
   TAB: Archivos — documentos adjuntados con fecha
   ================================================================ */
function FilesTab({ files }) {
  if (files.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center p-6 text-center text-fg-4 text-[12px]">
        No hay archivos adjuntados aún.<br />Los documentos enviados a Jarvis aparecerán aquí.
      </div>
    )
  }
  return (
    <div className="flex-1 overflow-y-auto p-3 flex flex-col gap-1">
      {files.map((f, i) => (
        <div key={i} className="flex items-center gap-3 px-3 py-2.5 rounded-md hover:bg-bg-2 transition cursor-default group">
          <div className="w-8 h-8 rounded-md bg-bg-3 flex items-center justify-center shrink-0">
            <Icon name="file" size={15} className="text-fg-3" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-[13px] text-fg-1 truncate">{f.name}</div>
            <div className="text-[11px] text-fg-4">Enviado por {f.from} · {f.time}</div>
          </div>
        </div>
      ))}
    </div>
  )
}

/* ================================================================
   TAB: Código — snippets que Jarvis ha generado con fecha
   ================================================================ */
function CodeTab({ snippets }) {
  const [expanded, setExpanded] = useState(null)

  if (snippets.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center p-6 text-center text-fg-4 text-[12px]">
        No hay código generado aún.<br />Los scripts y snippets de Jarvis aparecerán aquí.
      </div>
    )
  }
  return (
    <div className="flex-1 overflow-y-auto p-3 flex flex-col gap-2">
      {snippets.map((s, i) => (
        <div key={i} className="rounded-md border border-border overflow-hidden">
          <button
            type="button"
            onClick={() => setExpanded(expanded === i ? null : i)}
            className="w-full flex items-center gap-2.5 px-3 py-2.5 text-left hover:bg-bg-2 transition"
          >
            <div className="w-6 h-6 rounded bg-bg-3 flex items-center justify-center shrink-0">
              <span className="text-fg-3 text-[10px] font-mono">{'</>'}</span>
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-[12px] text-fg-1 truncate">{s.context || 'Snippet'}</div>
              <div className="text-[10px] text-fg-4">{s.time}</div>
            </div>
            <span className={'text-fg-4 text-[11px] transition-transform ' + (expanded === i ? 'rotate-90' : '')}>▶</span>
          </button>
          {expanded === i && (
            <div className="border-t border-border">
              <pre className="p-3 bg-bg-0 font-mono text-[11.5px] leading-[1.6] text-[hsl(220,15%,85%)] overflow-x-auto max-h-[300px] overflow-y-auto">
                <code>{s.code}</code>
              </pre>
              <div className="px-3 py-1.5 bg-bg-2 flex items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={() => { try { navigator.clipboard.writeText(s.code) } catch {} }}
                  className="text-[10px] text-fg-3 hover:text-fg-1 transition font-mono"
                >
                  Copiar
                </button>
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

/* ================================================================
   Componentes de soporte
   ================================================================ */
function SmallBtn({ children, title, onClick }) {
  return (
    <button type="button" title={title} onClick={onClick}
      className="inline-flex items-center justify-center w-[30px] h-[30px] rounded-md text-fg-3 hover:bg-bg-3 hover:text-fg-1 transition"
    >{children}</button>
  )
}

function TypingIndicator() {
  return (
    <div className="flex items-center gap-1.5 text-fg-3 text-[12px] animate-pulse">
      <span className="w-1.5 h-1.5 rounded-full bg-fg-3" />
      <span className="w-1.5 h-1.5 rounded-full bg-fg-3" />
      <span className="w-1.5 h-1.5 rounded-full bg-fg-3" />
      <span className="ml-1 font-mono text-[11px]">Jarvis</span>
    </div>
  )
}

function Message({ who, time, body, tool, file, code, error }) {
  const isJarvis = who === 'jarvis'
  const alignClass = isJarvis ? 'self-start items-start' : 'self-end items-end'
  const bubbleBase = 'rounded-lg px-3 py-2 text-[13.5px] leading-[1.55] whitespace-pre-wrap max-w-full'
  const bubbleClass = error
    ? bubbleBase + ' bg-[hsla(0,80%,60%,0.1)] border-l-2 border-[var(--err)] text-[var(--err)]'
    : isJarvis
      ? bubbleBase + ' bg-[var(--accent-muted)] border-l-2 border-[var(--accent)] text-fg-1'
      : bubbleBase + ' bg-bg-3 text-fg-1'

  return (
    <div className={'flex flex-col gap-1.5 max-w-[85%] ' + alignClass}>
      <div className="flex items-center gap-1.5 text-[11px] text-fg-4 px-1">
        <span className={isJarvis ? 'text-fg-1 font-semibold text-[12px]' : 'text-fg-2 font-semibold text-[12px]'}>
          {isJarvis ? 'Jarvis' : 'Usted'}
        </span>
        <span className="text-fg-4">·</span>
        <span>{time}</span>
      </div>

      {tool && (
        <div className="inline-flex items-center gap-2 px-2.5 py-1.5 bg-bg-2 border border-border rounded-md font-mono text-[11.5px] text-fg-2">
          <span className="w-1.5 h-1.5 rounded-full bg-[var(--ok)]" />
          <span className="text-fg-1">{tool.name}</span>
          <span className="text-fg-3">{tool.meta}</span>
        </div>
      )}

      {body && (
        <div className={bubbleClass}>
          {body}
          {file && (
            <div className="mt-1.5 inline-flex items-center gap-1.5 px-2 py-1 bg-bg-0/40 border border-border rounded-md text-[11.5px] text-fg-2">
              <Icon name="file" size={12} className="text-fg-3" />
              {file}
            </div>
          )}
        </div>
      )}

      {code && (
        <pre className="mt-1 p-3 bg-bg-0 border border-border rounded-lg font-mono text-[12px] leading-[1.6] text-[hsl(220,15%,85%)] overflow-x-auto">
          <code>{code}</code>
        </pre>
      )}
    </div>
  )
}
