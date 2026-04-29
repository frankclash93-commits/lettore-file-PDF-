import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
from pypdf import PdfReader
import ollama
import threading
import sqlite3
import json
import os
import time
import requests
import subprocess
import re
import psutil
import sys

try:
    import customtkinter as ctk
    CTK_AVAILABLE = True
except Exception:
    CTK_AVAILABLE = False
    
def avvia_e_forza_gpu():
    try:
        print("Resettando Ollama per attivare la GPU (se presente)...")
        if os.name == 'nt':
            subprocess.run("taskkill /F /IM ollama.exe /T", shell=True,
                        stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)

        check_gpu = ""
        try:
            if os.name == 'nt':
                check_gpu = subprocess.check_output("wmic path win32_VideoController get name", shell=True).decode()
            else:
                try:
                    check_gpu = subprocess.check_output("lspci", shell=True).decode()
                except Exception:
                    check_gpu = ""
        except Exception:
            check_gpu = ""

        if "AMD" in check_gpu.upper() or "RADEON" in check_gpu.upper():
            print("GPU AMD Rilevata. Configurazione Vulkan...")
            os.environ["OLLAMA_VULKAN"] = "1"
            os.environ["HSA_OVERRIDE_GFX_VERSION"] = "11.0.0"

        os.environ.setdefault("OLLAMA_MODELS", os.path.expanduser("~/.ollama/models"))

        print("Lancio del server Ollama con accelerazione hardware (se disponibile)...")
        popen_kwargs = {"env": os.environ}
        if os.name == 'nt':
            popen_kwargs["creationflags"] = subprocess.CREATE_NEW_CONSOLE
        try:
            subprocess.Popen(["ollama", "serve"], **popen_kwargs)
        except FileNotFoundError:
            print("Comando 'ollama' non trovato: assicurati che Ollama sia installato e nel PATH.")
        except Exception as e:
            print(f"Errore avvio Ollama: {e}")

        print("Attesa inizializzazione (5 secondi)...")
        time.sleep(5)
    except Exception as e:
        print(f"Errore durante l'avvio forzato: {e}")
        traceback.print_exc()

# --- CONFIGURAZIONE ESTETICA ---
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

ACCENT = "#03caf6"
PANEL = "#182437"
BG = "#010610"

# --- 1. MOTORE SMART BRIDGE (WEB) ---
class SmartBridge:
    def __init__(self):
        self.session = requests.Session()

    def ask(self, prompt):
        url = "https://text.pollinations.ai/"
        payload = {
            "messages": [{"role": "user", "content": prompt}],
            "model": "openai",
            "jsonMode": False
        }
        try:
            resp = self.session.post(url, json=payload, timeout=40)
            if resp.status_code == 200:
                testo = resp.text
                # Se la risposta contiene JSON (come quella che hai ricevuto), la puliamo
                try:
                    data = json.loads(testo)
                    # Cerchiamo di prendere solo il contenuto del messaggio
                    return data.get('content', testo)
                except:
                    return testo
            return f"Errore (Codice {resp.status_code})"
        except Exception as e:
            return f"Errore connessione: {str(e)}"

# --- 2. FUNZIONI DI SISTEMA E CMD ---
def suggerisci_modello():
    ram_gb = round(psutil.virtual_memory().total / (1024**3))
    gpu_nome = "Non rilevata"
    try:
        if os.name == 'nt':
            gpu_info = subprocess.check_output("wmic path win32_VideoController get name", shell=True).decode().split('\n')
            gpu_nome = gpu_info[1].strip() if len(gpu_info) > 1 else "Non rilevata"
        else:
            gpu_nome = subprocess.check_output("lspci | grep -i vga", shell=True).decode()
    except: pass

    if any(x in gpu_nome.upper() for x in ["NVIDIA", "AMD", "RADEON"]):
        if ram_gb >= 10:
            return "llama3", f" Ottimo (GPU + {ram_gb}GB RAM)"
        return "phi3:mini", f" Buono (GPU + {ram_gb}GB RAM)"
    else:
        if ram_gb <= 8:
            return "tinyllama", f" Base (No GPU + {ram_gb}GB RAM)"
        return "phi3:mini", f" Standard (No GPU + {ram_gb}GB RAM)"

def installa_modello_cmd(modello):
    if os.name == 'nt':
        # Apre una nuova finestra CMD e avvia il pull
        subprocess.Popen(f'start cmd /k "echo APEX LEDGER - INSTALLAZIONE {modello.upper()} && ollama pull {modello}"', shell=True)
    else:
        subprocess.Popen(['gnome-terminal', '--', 'bash', '-c', f'ollama pull {modello}; exec bash'])

# --- 3. APP PRINCIPALE ---
class ApexLedgerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("APEX LEDGER | Hybrid Intelligence 2026")
        self.geometry("1920x1080")
        
        self.bridge = SmartBridge()
        self.pdf_text = ""
        self.mode = "LOCALE"
        self.modello_locale, self.diagnosi_testo = suggerisci_modello()
        
        self.history = []  # Lista per memorizzare la conversazione
        
        self.init_db()
        self.setup_ui()
        self.auto_start_ollama()

    def init_db(self):
        conn = sqlite3.connect('apex_ledger_v3.db')
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS fatture 
                (id INTEGER PRIMARY KEY AUTOINCREMENT, fornitore TEXT, 
                importo REAL, scadenza TEXT, note TEXT, data_reg TEXT)''')
        conn.commit()
        conn.close()

    def auto_start_ollama(self):
        """Tenta di avviare il server Ollama in background (silenzioso)"""
        try:
            subprocess.Popen(["ollama", "serve"], 
                             creationflags=0x08000000 if os.name == 'nt' else 0,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except: pass

    def setup_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- SIDEBAR ---
        self.sidebar = ctk.CTkFrame(self, width=300, fg_color=BG, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        
        ctk.CTkLabel(self.sidebar, text="APEX LEDGER", font=("Segoe UI", 24, "bold"), text_color=ACCENT).pack(pady=(30, 10))
        ctk.CTkLabel(self.sidebar, text="Hybrid System v3.5", font=("Segoe UI", 10), text_color="gray").pack(pady=(0, 20))

        # Pannello Manutenzione/Diagnosi
        self.maint_frame = ctk.CTkFrame(self.sidebar, fg_color=PANEL, corner_radius=12)
        self.maint_frame.pack(fill="x", padx=15, pady=10)
        
        ctk.CTkLabel(self.maint_frame, text="DIAGNOSI HARDWARE", font=("Segoe UI", 11, "bold"), text_color=ACCENT).pack(pady=(10, 5))
        ctk.CTkLabel(self.maint_frame, text=self.diagnosi_testo, font=("Segoe UI", 10), wraplength=250).pack(pady=5)
        
        self.btn_download = ctk.CTkButton(self.maint_frame, text=f"SCARICA {self.modello_locale.upper()}", 
        fg_color="#059669", hover_color="#047857", height=35,
        command=lambda: installa_modello_cmd(self.modello_locale))
        self.btn_download.pack(pady=10, padx=15)

        # Modalità Operativa
        ctk.CTkLabel(self.sidebar, text="MODALITÀ AI", font=("Segoe UI", 12, "bold")).pack(pady=(20, 5))
        self.mode_var = tk.StringVar(value="LOCALE")
        self.seg_button = ctk.CTkSegmentedButton(self.sidebar, values=["AI LOCALE", "AI SMART"], 
                                                command=self.set_mode, variable=self.mode_var)
        self.seg_button.pack(pady=5, padx=20, fill="x")

        # Azioni File
        ctk.CTkButton(self.sidebar, text="📂 CARICA PDF", command=self.load_pdf).pack(pady=(30, 10), padx=20, fill="x")
        self.btn_analyze = ctk.CTkButton(self.sidebar, text="⚡ ESTRAI DATI", fg_color="#047857", 
        state="disabled", command=self.analyze_invoice)
        self.btn_analyze.pack(pady=10, padx=20, fill="x")

        # --- AREA CHAT ---
        self.chat_area = ctk.CTkTextbox(self, font=("Segoe UI", 15), corner_radius=15, border_width=1, border_color="#70a7ff")
        self.chat_area.grid(row=0, column=1, padx=20, pady=(20, 100), sticky="nsew")
        self.chat_area.insert("end", f"SISTEMA: Pronto. Modello locale suggerito: {self.modello_locale}.\n", "sys")

        # --- INPUT ---
        self.input_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.input_frame.grid(row=0, column=1, padx=20, pady=25, sticky="s")
        self.entry = ctk.CTkEntry(self.input_frame, placeholder_text="Chiedi all'AI o analizza il PDF...", width=650, height=50)
        self.entry.pack(side="left", padx=10)
        self.entry.bind("<Return>", lambda e: self.send_message())
        ctk.CTkButton(self.input_frame, text="INVIA", width=100, height=50, command=self.send_message).pack(side="right") 

    def set_mode(self, m):
        self.mode = m
        self.chat_area.insert("end", f"\n[SISTEMA] Modalità impostata su: {m}\n")

    def load_pdf(self):
        path = filedialog.askopenfilename(filetypes=[("PDF", "*.pdf"), ("Text", "*.txt")])
        if path:
            try:
                if path.endswith('.pdf'):
                    reader = PdfReader(path)
                    self.pdf_pages = [p.extract_text() or "" for p in reader.pages]
                    self.pdf_text = " ".join(self.pdf_pages)
                elif path.endswith('.txt'):
                    with open(path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    self.pdf_pages = [content]
                    self.pdf_text = content
                
                self.chat_area.insert("end", f"\n[FILE] Caricato {os.path.basename(path)} ({len(self.pdf_pages)} pag.)\n")
                self.btn_analyze.configure(state="normal")
            except Exception as e:
                messagebox.showerror("Errore", f"Impossibile leggere il file: {e}")

    def send_message(self):
        msg = self.entry.get()
        if not msg: return
        self.entry.delete(0, "end")
        self.chat_area.insert("end", f"\n👤 TU: {msg}\n")
        threading.Thread(target=self._ai_logic, args=(msg,)).start()

    def _ai_logic(self, query):
        # 1. RECUPERO CONTESTO PDF (RAG)
        parole_chiave = [p.lower() for p in query.split() if len(p) > 3]
        pdf_context = ""
        if hasattr(self, 'pdf_pages') and self.pdf_pages:
            pagine_trovate = [pag for pag in self.pdf_pages if any(kw in pag.lower() for kw in parole_chiave)]
            pdf_context = "\nDOC: " + "\n".join(pagine_trovate[:2]) if pagine_trovate else "\nDOC: " + "\n".join(self.pdf_pages[:1])

        # 2. COSTRUZIONE STORICO (Ultimi 4 scambi per non sovraccaricare)
        # Trasformiamo la storia in un formato leggibile dall'AI
        memoria_testo = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in self.history[-4:]])

        # 3. PROMPT FINALE
        prompt = (
            "Sei TextBI, un assistente basato su dati reali. "
            "IMPORTANTE: Non inventare fatti non accaduti ma basati solo su dati reali.\n\n"
            "REGOLE:Se non conosci un dato aggiornato al 2026, "
            "riferisciti agli ultimi dati certi (2024/2025) senza fare congetture.\n\n"
            f"CONTESTO PDF: {pdf_context}\n"
            f"STORICO CHAT:\n{memoria_testo}\n"
            f"DOMANDA ATTUALE: {query}\n"
            "Rispondi in modo asciutto e preciso, solo testo, niente JSON."
        )

        # 4. INVIO ALL'AI
        risposta_finale = ""
        if self.mode == "AI SMART":
            self.chat_area.insert("end", "✨ SMART AI: ")
            risposta_finale = self.bridge.ask(prompt[:6000])
            self.chat_area.insert("end", f"{risposta_finale}\n")
        else:
            self.chat_area.insert("end", f"AI LOCALE ({self.modello_locale}): ")
            try:
                stream = ollama.chat(model=self.modello_locale, messages=[{'role': 'user', 'content': prompt}], stream=True)
                for chunk in stream:
                    txt = chunk['message']['content']
                    risposta_finale += txt
                    self.chat_area.insert("end", txt)
                self.chat_area.insert("end", "\n")
            except Exception as e:
                self.chat_area.insert("end", f"\nErrore locale: {e}\n")

        # 5. AGGIORNAMENTO MEMORIA
        self.history.append({"role": "user", "content": query})
        self.history.append({"role": "assistant", "content": risposta_finale})
        
        # 2. PROMPT IBRIDO
        prompt = (
            "Sei APEX LEDGER, un assistente AI. "
            f"{context if context else 'Nessun documento caricato.'}\n\n"
            "REGOLE: Usa il documento sopra per rispondere se pertinente, "
            "altrimenti usa le tue conoscenze. Rispondi sempre in italiano.\n\n"
            f"DOMANDA: {query}"
        )

        # 3. INVIO ALL'AI
        if self.mode == "AI SMART":
            self.chat_area.insert("end", "✨ SMART AI: ")
            # Limite a 5000 per evitare errori 502/Timeout su Pollinations
            res = self.bridge.ask(prompt[:5000]) 
            self.chat_area.insert("end", f"{res}\n")
        else:
            self.chat_area.insert("end", f"LOCALE ({self.modello_locale}): ")
            try:
                stream = ollama.chat(model=self.modello_locale, 
                                     messages=[{'role': 'user', 'content': prompt}], 
                                     stream=True)
                for chunk in stream:
                    self.chat_area.insert("end", chunk['message']['content'])
                self.chat_area.insert("end", "\n")
            except Exception as e:
                self.chat_area.insert("end", f"\nErrore locale: {e}\n")
        
        # 2. PROMPT IBRIDO (Sblocca la conoscenza generale)
        prompt = (
            "Sei TextBI, un assistente AI avanzato. "
            f"{context if context else 'Nessun documento rilevante caricato.'}\n\n"
            "REGOLE: \n"
            "1. Se la domanda riguarda il documento sopra, rispondi usando quei dati.\n"
            "2. Se la domanda è generale o fuori contesto, rispondi usando la tua conoscenza libera.\n"
            "3. Non dire mai 'non ho informazioni' se puoi rispondere con la tua cultura generale.\n\n"
            f"DOMANDA: {query}"
        )

        # 3. INVIO ALL'AI (SMART o LOCALE)
        if self.mode == "AI SMART":
            self.chat_area.insert("end", "✨ SMART AI: ")
            res = self.bridge.ask(prompt[:10000]) 
            self.chat_area.insert("end", f"{res}\n")
        else:
            self.chat_area.insert("end", f"AI LOCALE ({self.modello_locale}): ")
            try:
                stream = ollama.chat(model=self.modello_locale, 
                messages=[{'role': 'user', 'content': prompt}], 
                stream=True)
                for chunk in stream:
                    self.chat_area.insert("end", chunk['message']['content'])
                self.chat_area.insert("end", "\n")
            except Exception as e:
                self.chat_area.insert("end", f"\nOllama non risponde: {e}\n")

    def analyze_invoice(self):
        self.chat_area.insert("end", "\n Analisi contabile automatica...\n")
        threading.Thread(target=self._extract_logic).start()

    def _extract_logic(self):
        prompt = "Analizza questa fattura ed estrai SOLO un JSON: {\"fornitore\":\"\", \"importo\":0.0, \"scadenza\":\"DD/MM/YYYY\", \"note\":\"\"}"
        try:
            # Per estrazione dati usiamo il modello locale suggerito
            res = ollama.chat(model=self.modello_locale, messages=[{'role': 'user', 'content': prompt + "\n\n" + self.pdf_text[:7000]}])
            raw = res['message']['content']
            
            match = re.search(r'\{.*\}', raw, re.DOTALL)
            if match:
                data = json.loads(match.group())
                self.save_invoice(data)
                self.chat_area.insert("end", f"REGISTRATA: {data['fornitore']} - €{data['importo']}\n")
            else:
                self.chat_area.insert("end", f"Formato AI non valido. Risposta: {raw[:100]}...\n")
        except Exception as e:
            self.chat_area.insert("end", f"Errore: {e}\n")

    def save_invoice(self, data):
        try:
            conn = sqlite3.connect('apex_ledger_v3.db')
            c = conn.cursor()
            c.execute("INSERT INTO fatture (fornitore, importo, scadenza, note, data_reg) VALUES (?,?,?,?,?)",
            (data.get('fornitore'), data.get('importo'), data.get('scadenza'), data.get('note'), time.strftime("%d/%m/%Y")))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Errore DB: {e}")
            
try:
        t_gpu = threading.Thread(target=avvia_e_forza_gpu, daemon=True)
        t_gpu.start()
except Exception as e:
        print(f"Errore avvio GPU: {e}")

if __name__ == "__main__":
    app = ApexLedgerApp()
    app.mainloop()
    