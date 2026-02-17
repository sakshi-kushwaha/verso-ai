# **Verso**

## Learn Smarter, Scroll Better

An AI-Powered App That Transforms Documents into Reels-Style Learning

PRD Submitted: 15 February 2026

Build: 16-22 Feb | Demo: 23 Feb 2026

Team Size: 3

---

## **1. Problem Statement**

### **What problem are we solving?**

People of all ages struggle to engage with long-form educational and professional content like textbooks, research papers, and documents. Traditional reading is time-consuming, passive, and mentally draining — leading to poor retention. You either read the whole thing or miss important points, with no engaging format to help you along the way.

### **Who is the target user?**

Learners of all age groups — students, working professionals, and lifelong learners — who need to absorb knowledge from lengthy PDFs and documents, especially those who prefer bite-sized, scrollable content over dense, static pages.

### **Why does this problem matter?**

- People retain only ~10-20% of what they read passively, yet documents remain the primary way we share knowledge
- Short-form scrollable content has proven to be highly engaging, but there's no bridge between that experience and educational or professional material
- Existing tools either over-summarize (losing important details) or just highlight text (which is still passive and boring)
- Documents remain the default format across schools, colleges, and workplaces — yet the reading experience hasn't evolved in decades

> *Verso bridges this gap by transforming any PDF or Word document into swipeable, reels-style learning content with flashcards, personalized onboarding, and conversational Q&A — powered entirely by local AI. It works fully offline, keeps user data private, and makes studying feel like scrolling a feed.*

---

## **2. Proposed Solution**

### **What is Verso?**

Verso is a local-first, AI-powered web application that converts PDF and DOCX documents into a scrollable feed of short, swipeable learning reels. It runs entirely offline, keeping all user data private.

### **What will it do?**

- **Authenticated Experience** — User login to maintain personalized profiles and progress across sessions
- **Customized Onboarding** — Detect user learning preferences (visual, auditory, reading) and adapt content style via an onboarding flow
- **Document Parsing** — Accept PDF and DOCX uploads and progressively parse them into sections, detecting document type automatically
- **Reel Generation** — Produce structured learning reels from your document — titles, categorized summaries, keywords, and page references
- **Flashcards + Reels** — Generate flashcards alongside reels for active recall and self-testing
- **Chat Conversation + Summary** — Q&A chat over uploaded documents with conversation summaries saved for later
- **Swipeable Feed** — Full-screen vertical swipeable reel experience, just like scrolling a social feed
- **Download & Save** — Bookmark reels, save flashcards, and download content for offline use
- **Progress Tracking** — Track reading and viewing progress across uploads

### **What will it NOT do?**

- Does not support formats other than PDF and DOCX — no web links, videos, or ebooks
- Does not allow real-time collaboration or sharing with others
- Does not sync across devices — everything stays on your local machine
- Does not extract images or diagrams from documents — text content only
- Does not generate video or animated reels — reels are text-based with optional audio narration
- Does not guarantee 100% accuracy — content is AI-generated and may occasionally contain errors
- Does not require internet — runs fully offline with no cloud dependency

> *Scope Boundary: Verso is a learning and review tool, not a document editor or exam platform. It takes documents in and produces engaging reels, flashcards, and Q&A — nothing more.*

---

## **3. Core Features (MVP)**

### **F1: Authentication**

Simple login and signup using name and password. No email verification — just basic auth to tie preferences, progress, and bookmarks to a user profile.

### **F2: Customized Onboarding**

First-time users complete a short quiz capturing their learning style (visual, auditory, reading) and content preferences. This profile drives how reels are generated:

- **Visual learners** get structured bullet points and clear formatting
- **Auditory learners** get conversational narration scripts
- **Reading-focused learners** get detailed, paragraph-style summaries

Document type is auto-detected (educational, technical, fiction, business) to further tailor content.

### **F3: Document Upload & Progressive Parsing**

Upload a PDF or DOCX (max 50 MB). The document is parsed progressively in the background so the UI stays responsive — reels appear incrementally as sections are processed, not after the entire document is done. Users start consuming content within seconds of uploading.

### **F4: Reel Generation**

Each section of the document is transformed into a structured learning reel containing:

- Title
- Categorized summary
- Topic category badge
- Keywords
- Page reference back to the source

Reel count scales with document length (~1 reel per 4 pages). Content style adapts based on the user's learning preference.

### **F5: Flashcards + Reels**

Alongside each reel, the AI generates flashcards (question/answer pairs) for active recall. Users swipe reels for passive learning and flip to flashcard mode for self-testing from a dedicated tab.

### **F6: Chat Q&A + Summary**

After a document is processed, users can ask questions about it via a chat interface. Answers are grounded in the actual document content with source references. Conversations are limited in length, and summaries are saved for later review.

### **F7: Swipeable Feed UI**

Reels are displayed in a full-screen vertical swipeable feed. Each reel shows its title, summary, category badge, page reference, and an audio play button. Paginated loading with infinite scroll keeps the experience smooth.

### **F8: Download & Save**

Bookmark any reel or flashcard for later review (Saved tab). Download content as bundled offline packages. Audio narration is generated and cached automatically.

> *Design Principle: Verso generates reels progressively — users start consuming content within seconds of uploading, not after the entire document is processed. Every feature works offline with zero cloud dependency.*

---

## **4. User Flows**

### **Flow 1: Sign Up & Onboarding**

1. User opens the app and lands on the Login/Signup page
2. User creates an account with a name and password
3. First-time users are guided through a short onboarding quiz to capture learning style and preferences
4. Preferences are saved to their profile and used to personalize all future content
5. User is redirected to the Upload page

### **Flow 2: Upload & Generate Reels**

1. User selects a PDF or DOCX file to upload (max 50 MB)
2. A progress indicator appears immediately — no blank waiting screen
3. Reels start appearing in the feed within seconds as each section is processed
4. Flashcards are generated alongside each reel
5. Once fully processed, the document becomes available for Chat Q&A
6. The uploaded file is not stored permanently — only the generated content is kept

### **Flow 3: Consume the Feed**

1. User opens the reel feed and swipes vertically through full-screen reel cards
2. Each reel shows a title, summary, category badge, keywords, and page reference
3. Users can tap the audio button to hear the reel narrated
4. Infinite scroll loads more reels automatically
5. Viewing progress is tracked per reel

### **Flow 4: Chat Q&A**

1. After a document is fully processed, the Chat tab becomes available
2. User types a question about the document
3. The AI returns a grounded answer with references to specific parts of the document
4. Conversations are saved and can be summarized for later review

### **Flow 5: Bookmarks, Flashcards & Download**

1. Tap the bookmark icon on any reel or flashcard to save it
2. Access all saved items from the Bookmarks tab
3. Use the Flashcards tab for a dedicated flip-card self-testing experience
4. Download bundled reels, flashcards, and audio as a zip package for offline use

---

## **5. Success Metrics**

### **Performance**

| Metric | Target |
|--------|--------|
| Time to first reel after upload | < 90 seconds |
| Full processing (20-page document) | < 3 minutes |
| Feed load time | < 500ms |
| Chat Q&A response time | < 60 seconds |
| App startup | < 5 seconds |
| Onboarding completion | < 30 seconds |

### **Quality**

| Metric | Target |
|--------|--------|
| Reel generation success rate | > 90% of sections produce valid reels |
| Content relevance | Reels accurately reflect source material |
| Flashcard quality | Accurate, useful question/answer pairs |
| Audio narration coverage | > 95% of reels have audio |
| Chat Q&A relevance | Answers grounded in actual document content |

### **User Experience**

| Metric | Target |
|--------|--------|
| Pipeline never hangs or gets stuck | 100% completion across test documents |
| Graceful failure handling | App continues working even if individual sections fail |
| Progress feedback | User sees progress within 10 seconds of upload |
| Feed smoothness | No stutter or jank while swiping |
| Mobile usability | Swipe works on touch devices |

---

## **6. Known Limitations**

| Limitation | Impact | Why It's Acceptable for MVP |
|-----------|--------|----------------------------|
| Processing takes 2-4 minutes for a 20-page doc | Users wait for full results | Background processing and progressive delivery make it feel faster |
| Audio narration sounds robotic | Less pleasant listening experience | Audio is supplementary — visual reels are the primary experience |
| No OCR for scanned documents | Image-based PDFs produce no content | Text-based documents are the target use case |
| English-optimized | Other languages may produce lower quality results | Prompts and narration are tuned for English |
| Simple login (not production-grade security) | Basic authentication only | Acceptable for a local-first, single-user MVP |
| Fixed reel format | Every reel looks the same | Keeps output consistent and reliable |
| Single-user, single-device | No sync or collaboration | Local-first privacy is a core design choice |

---

## **7. Risks**

| Risk | Likelihood | Mitigation |
|------|-----------|-----------|
| AI takes too long to respond | Medium | Each section is processed independently with timeouts — one slow section doesn't block the rest |
| AI produces poorly formatted output | Medium | Multi-level fallback: bad sections are skipped, others continue normally |
| Upload gets stuck processing | Medium | Multiple safety layers ensure processing always completes. Users can re-upload. |
| Very large document (500+ pages) | Low | 50 MB file size limit. Section cap controls total processing. |
| Multiple uploads at once | Low | Processed one at a time. No crash, just queued. |

---

## **8. Stretch Goals**

These will only be attempted if all core features (F1-F8) are complete and stable.

| # | Goal | Description |
|---|------|-------------|
| S1 | **Spaced Repetition** | Resurface reels and flashcards at the right time to help users retain knowledge long-term instead of forgetting after one read |
| S2 | **Smart Reel Ordering** | Reorder reels based on what users have bookmarked, skipped, or spent time on — most relevant content comes first |
| S3 | **Smarter Section Splitting** | Better handling of documents without clear chapter headings, so reels break at natural points |
| S4 | **Better Voice Narration** | Replace the robotic voice with a more natural-sounding narrator |
| S5 | **Document Library** | Upload multiple documents and browse a personal library of past uploads |
| S6 | **Export & Share** | Export saved reels and flashcards as a printable study summary |
| S7 | **More File Formats** | Support for EPUB and plain text files |
| S8 | **Image Extraction** | Display figures, charts, and diagrams from documents on reel cards |
| S9 | **Voice Q&A** | Ask questions by speaking and hear answers read back like a study companion |

---

> *Verso is not just a summarizer. It's a new way to learn from any document — one reel at a time. Every feature is designed around real learning science, real device constraints, and real user behavior.*
