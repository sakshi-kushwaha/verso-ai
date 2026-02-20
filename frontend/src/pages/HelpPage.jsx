import { useState } from 'react'
import { Help, ChevDown } from '../components/Icons'

const faqs = [
  {
    q: 'How do I upload a document?',
    a: 'Go to the Upload page from the sidebar. Drag & drop or click to select a PDF or DOCX file. Verso AI will process it in the background — parsing, analyzing, and extracting key concepts.',
  },
  {
    q: 'What content does AI generate?',
    a: 'Once your document is processed, Verso AI creates short bites (bite-sized summaries), flashcards for studying, and a full document summary. You can find all of these in your feed and collections.',
  },
  {
    q: 'How do bites and the feed work?',
    a: 'Your feed shows AI-generated bites from your uploaded documents. Swipe through them like a social feed. Each bite covers a key concept from your document with a short summary.',
  },
  {
    q: 'How do flashcards work?',
    a: 'Flashcards are auto-generated from your documents. Tap to flip between question and answer. You can bookmark cards you want to revisit later.',
  },
  {
    q: 'How does Chat Q&A work?',
    a: 'Open Chat from the feed or a collection. Ask any question about your document and get AI-powered answers with source citations. Start a new session anytime you need a fresh conversation.',
  },
  {
    q: 'How do bookmarks work?',
    a: 'Tap the bookmark icon on any bite or flashcard to save it. View all your saved items on the Bookmarks page accessible from the sidebar.',
  },
  {
    q: 'Can I listen to content?',
    a: 'Yes! Document summaries and bite narrations have audio playback. Tap the volume icon to listen instead of reading.',
  },
  {
    q: 'What are Collections?',
    a: 'Collections is where all your uploaded documents live. Each collection shows the generated bites, flashcards, and summary for that document. Access it from the sidebar.',
  },
]

function AccordionItem({ q, a, open, onToggle, delay }) {
  return (
    <div
      className="bg-surface rounded-xl border border-border fade-up"
      style={{ animationDelay: `${delay}s` }}
    >
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between p-5 text-left cursor-pointer"
      >
        <span className="font-display font-semibold text-sm pr-4">{q}</span>
        <span
          className={`text-text-muted shrink-0 transition-transform duration-200 ${open ? 'rotate-180' : ''}`}
        >
          <ChevDown />
        </span>
      </button>
      {open && (
        <div className="px-5 pb-5 -mt-1">
          <p className="text-text-muted text-sm leading-relaxed">{a}</p>
        </div>
      )}
    </div>
  )
}

export default function HelpPage() {
  const [openIdx, setOpenIdx] = useState(null)

  return (
    <div className="max-w-xl mx-auto p-6 pt-10 fade-up">
      <div className="flex items-center gap-3 mb-1">
        <div className="w-9 h-9 rounded-xl bg-primary/10 flex items-center justify-center text-primary">
          <Help />
        </div>
        <h1 className="text-2xl font-bold font-display">Help</h1>
      </div>
      <p className="text-text-muted text-sm mb-8">Frequently asked questions about Verso AI</p>

      <div className="flex flex-col gap-3">
        {faqs.map((faq, i) => (
          <AccordionItem
            key={i}
            q={faq.q}
            a={faq.a}
            open={openIdx === i}
            onToggle={() => setOpenIdx(openIdx === i ? null : i)}
            delay={i * 0.06}
          />
        ))}
      </div>
    </div>
  )
}
