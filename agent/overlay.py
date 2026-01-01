import tkinter as tk
import logging
from datetime import datetime

try:
    from PIL import Image, ImageDraw, ImageTk
except ImportError:
    Image = None
    ImageDraw = None
    ImageTk = None

class OverlayHUD:
    """Agentic-style AI HUD: dark, minimal, robust chat overlay."""

    def __init__(self, agent_runner=None, title="Theta Ai", width=540, height=740, margin=16):
        self.agent_runner = agent_runner
        self.width = width
        self.height = height
        self.margin = margin

        # state
        self._voice_running = False
        self._task_running = False
        self.current_future = None
        self.typing_frame = None
        self.current_state = None
        self.state_label = None
        self.reasoning_expanded = False
        self.reasoning_frame = None
        self.last_reasoning = None
        self.reasoning_poll_id = None

        # --- DESIGN TOKENS ---
        self.radius_lg = 22

        self.color_bg = "#020617"
        self.color_panel = "#020617"
        self.color_panel_soft = "#020617"

        self.color_border_subtle = "#1f2937"

        self.color_text_primary = "#e5e7eb"
        self.color_text_muted = "#6b7280"
        self.color_text_soft = "#9ca3af"

        self.color_accent = "#4f46e5"
        self.color_accent_hover = "#6366f1"

        self.color_user_bubble = "#4f46e5"
        self.color_agent_bubble = "#020617"

        self.color_success = "#22c55e"
        self.color_warning = "#f59e0b"
        self.color_error = "#ef4444"

        self.font_sans = ("Segoe UI", 10)
        self.font_sans_sm = ("Segoe UI", 9)
        self.font_sans_md = ("Segoe UI", 11)
        self.font_sans_lg = ("Segoe UI Semibold", 13)

        # --- ROOT ---
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        try:
            self.root.attributes("-alpha", 0.98)
        except Exception:
            pass

        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = sw - self.width - self.margin
        y = sh - self.height - (self.margin + 40)
        self.root.geometry(f"{self.width}x{self.height}+{x}+{y}")
        self.root.configure(bg=self.color_bg)

        # rounded card (all corners)
        self.bg_canvas = tk.Canvas(self.root, bg=self.color_bg, highlightthickness=0, bd=0)
        self.bg_canvas.pack(fill="both", expand=True)
        self.root.update_idletasks()
       

        main = tk.Frame(self.bg_canvas, bg=self.color_panel, bd=0)
        self.main_window = self.bg_canvas.create_window(
            0, 0, anchor="nw", width=self.width, height=self.height, window=main
        )

        # --- HEADER ---
        header = tk.Frame(main, bg=self.color_panel, height=56, cursor="fleur")
        header.pack(fill="x")
        header.pack_propagate(False)

        self._drag_start_x = 0
        self._drag_start_y = 0
        header.bind("<Button-1>", self._start_drag)
        header.bind("<B1-Motion>", self._on_drag)

        left = tk.Frame(header, bg=self.color_panel)
        left.pack(side="left", padx=20, pady=10)
        left.bind("<Button-1>", self._start_drag)
        left.bind("<B1-Motion>", self._on_drag)

        # Load and display logo as avatar
        try:
            import os
            logo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "logo.png")
            if os.path.exists(logo_path) and Image and ImageTk:
                logo_img = Image.open(logo_path)
                logo_img = logo_img.resize((32, 32), Image.Resampling.LANCZOS)
                
                # Add rounded corners to logo
                radius = 8
                mask = Image.new('L', (32, 32), 0)
                mask_draw = ImageDraw.Draw(mask)
                mask_draw.rounded_rectangle((0, 0, 32, 32), radius=radius, fill=255)
                logo_img.putalpha(mask)
                
                self.avatar_photo = ImageTk.PhotoImage(logo_img)
                self.avatar_label = tk.Label(
                    left, image=self.avatar_photo, bg=self.color_panel,
                    cursor="fleur"
                )
                self.avatar_label.pack(side="left")
                self.avatar_label.bind("<Button-1>", self._start_drag)
                self.avatar_label.bind("<B1-Motion>", self._on_drag)
            else:
                raise FileNotFoundError("Logo not found or PIL not available")
        except Exception as e:
            # Fallback to canvas if logo loading fails
            self.avatar_canvas = tk.Canvas(
                left, width=32, height=32, bg=self.color_panel,
                highlightthickness=0, bd=0, cursor="fleur"
            )
            self.avatar_canvas.pack(side="left")
            # self._draw_avatar()
            self.avatar_canvas.bind("<Button-1>", self._start_drag)
            self.avatar_canvas.bind("<B1-Motion>", self._on_drag)

        title_container = tk.Frame(left, bg=self.color_panel)
        title_container.pack(side="left", padx=10)
        title_container.bind("<Button-1>", self._start_drag)
        title_container.bind("<B1-Motion>", self._on_drag)

        title_lbl = tk.Label(
            title_container, text=title, bg=self.color_panel,
            fg=self.color_text_primary, font=self.font_sans_lg
        )
        title_lbl.pack(anchor="w")

        self.status_label = tk.Label(
            title_container, text="Ready",
            bg=self.color_panel, fg=self.color_success,
            font=self.font_sans_sm
        )
        self.status_label.pack(anchor="w")

        controls = tk.Frame(header, bg=self.color_panel)
        controls.pack(side="right", padx=16, pady=8)

        # close button: full shutdown
        close_btn = tk.Button(
            controls, text="×", command=self.root.destroy,
            bd=0, relief="flat", cursor="hand2", width=2,
            bg=self.color_panel, fg=self.color_text_muted,
            activebackground=self.color_panel, font=("Segoe UI", 16)
        )
        close_btn.pack(side="left")
        close_btn.bind("<Enter>", lambda e: close_btn.config(fg=self.color_error))
        close_btn.bind("<Leave>", lambda e: close_btn.config(fg=self.color_text_muted))

        tk.Frame(main, bg=self.color_border_subtle, height=1).pack(fill="x")

        # --- CHAT ---
        self.chat_frame = tk.Frame(main, bg=self.color_panel)
        self.chat_frame.pack(fill="both", expand=True, padx=16, pady=(8, 8))

        self.chat_canvas = tk.Canvas(
            self.chat_frame, bg=self.color_panel, highlightthickness=0, bd=0
        )
        self.chat_canvas.pack(side="left", fill="both", expand=True)

        # SCROLLBAR REMOVED - Only mousewheel scrolling will work
        # scrollbar = tk.Scrollbar(
        #     self.chat_frame, orient="vertical", command=self.chat_canvas.yview,
        #     bg=self.color_panel, troughcolor=self.color_panel,
        #     highlightthickness=0, bd=0, activebackground=self.color_panel
        # )
        # scrollbar.pack(side="right", fill="y")
        # self.chat_canvas.configure(yscrollcommand=scrollbar.set)

        self.chat_container = tk.Frame(self.chat_canvas, bg=self.color_panel)
        self.canvas_frame = self.chat_canvas.create_window(
            (0, 0), window=self.chat_container, anchor="nw"
        )

        self.chat_container.bind("<Configure>", self._on_frame_configure)
        self.chat_canvas.bind("<Configure>", self._on_canvas_configure)
        self.chat_canvas.bind("<Enter>", lambda e: self._bind_mousewheel())
        self.chat_canvas.bind("<Leave>", lambda e: self._unbind_mousewheel())

        # --- INPUT (rounded strip + pill button) ---
        input_area = tk.Frame(main, bg=self.color_panel)
        input_area.pack(fill="x", padx=16, pady=(0, 16))

        input_container = tk.Frame(
            input_area, bg=self.color_panel_soft,
            highlightthickness=1, highlightbackground=self.color_border_subtle, bd=0
        )
        input_container.pack(fill="x")

        self.entry = tk.Entry(
            input_container, bg=self.color_panel_soft, fg=self.color_text_primary,
            insertbackground=self.color_accent, bd=0, relief="flat",
            font=self.font_sans_md
        )
        self.entry.pack(side="left", fill="x", expand=True, padx=14, pady=12)
        self.entry.bind("<Return>", self._on_send_or_stop)
        self.entry.bind("<KeyRelease>", self._on_entry_change)

        self._placeholder = "Give task..."
        self.entry.insert(0, self._placeholder)
        self.entry.configure(fg=self.color_text_muted)
        self.entry.bind("<FocusIn>", self._clear_placeholder)
        self.entry.bind("<FocusOut>", self._restore_placeholder)
        self.entry.bind("<Key>", self._clear_placeholder_on_key)

        # Load mic icons
        try:
            import os
            asset_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")
            
            # Mic icons
            inactive_mic_path = os.path.join(asset_path, "inactiveMic.png")
            active_mic_path = os.path.join(asset_path, "activeMic.png")
            
            if Image and ImageTk and os.path.exists(inactive_mic_path) and os.path.exists(active_mic_path):
                # Load and resize mic icons
                inactive_mic_img = Image.open(inactive_mic_path).resize((40, 40), Image.Resampling.LANCZOS)
                active_mic_img = Image.open(active_mic_path).resize((40, 40), Image.Resampling.LANCZOS)
                
                self.mic_photo_inactive = ImageTk.PhotoImage(inactive_mic_img)
                self.mic_photo_active = ImageTk.PhotoImage(active_mic_img)
                
                # Mic button
                self.mic_btn = tk.Button(
                    input_container, image=self.mic_photo_inactive, 
                    command=self._toggle_voice,
                    bg=self.color_panel_soft, bd=0, relief="flat",
                    cursor="hand2", highlightthickness=0
                )
                self.mic_btn.pack(side="right", padx=8, pady=6)
                self.mic_btn_inactive_photo = self.mic_photo_inactive
                self.mic_btn_active_photo = self.mic_photo_active
            else:
                raise FileNotFoundError("Mic icons not found")
        except Exception as e:
            # Fallback to canvas if icons not available
            self.mic_canvas = tk.Canvas(
                input_container, width=26, height=26, bg=self.color_panel_soft,
                highlightthickness=0, bd=0, cursor="hand2"
            )
            self.mic_canvas.pack(side="right", padx=8, pady=8)
            self.mic_canvas.bind("<Button-1>", lambda e: self._toggle_voice())
            self._draw_mic_icon(False)
            self._add_hover_canvas(self.mic_canvas)

        # Load send icon
        try:
            send_icon_path = os.path.join(asset_path, "send.png")
            if Image and ImageTk and os.path.exists(send_icon_path):
                send_img = Image.open(send_icon_path).resize((40, 40), Image.Resampling.LANCZOS)
                self.send_photo = ImageTk.PhotoImage(send_img)
                
                # Send button with image
                self.send_btn = tk.Button(
                    input_container, image=self.send_photo,
                    command=self._on_send,
                    bg="#111827", bd=0, relief="flat",
                    cursor="arrow", highlightthickness=0,
                    state="disabled",
                )
                self.send_btn.pack(side="right", padx=8, pady=6)
                
                def on_enter(e):
                    if not self._task_running and self.send_btn["state"] == "normal":
                        self.send_btn.config(bg="#1f2937")

                def on_leave(e):
                    if not self._task_running and self.send_btn["state"] == "normal":
                        self.send_btn.config(bg="#111827")

                self.send_btn.bind("<Enter>", on_enter)
                self.send_btn.bind("<Leave>", on_leave)
                
                # Load pause icon
                pause_icon_path = os.path.join(asset_path, "pause.png")
                if os.path.exists(pause_icon_path):
                    pause_img = Image.open(pause_icon_path).resize((40, 40), Image.Resampling.LANCZOS)
                    self.pause_photo = ImageTk.PhotoImage(pause_img)
                    
                    # Pause button (hidden by default)
                    self.pause_btn = tk.Button(
                        input_container, image=self.pause_photo,
                        command=self._on_stop_button,
                        bg="#06b6d4", bd=0, relief="flat",
                        cursor="hand2", highlightthickness=0,
                    )
                    # Don't pack yet - will show when task runs
                else:
                    self.pause_btn = None
            else:
                raise FileNotFoundError("Send icon not found")
        except Exception:
            # Fallback to text button
            self.send_btn = tk.Button(
                input_container,
                text="↑",
                command=self._on_send,
                bg="#111827",
                fg=self.color_text_soft,
                bd=0,
                width=3,
                font=("Segoe UI", 13, "bold"),
                cursor="arrow",
                relief="flat",
                state="disabled",
            )
            self.send_btn.pack(side="right", padx=(4, 8), pady=6)
            self.pause_btn = None

            def on_enter(e):
                if not self._task_running and self.send_btn["state"] == "normal":
                    self.send_btn.config(bg="#1f2937")

            def on_leave(e):
                if not self._task_running and self.send_btn["state"] == "normal":
                    self.send_btn.config(bg="#111827")

            self.send_btn.bind("<Enter>", on_enter)
            self.send_btn.bind("<Leave>", on_leave)

        # --- LOGGING TO HUD ---
        class HUDHandler(logging.Handler):
            def __init__(self, hud):
                super().__init__()
                self.hud = hud

            def emit(self, record):
                try:
                    msg = self.format(record)
                    level = record.levelno
                    style = "info"
                    if level >= logging.ERROR:
                        style = "error"
                    elif level >= logging.WARNING:
                        style = "warning"
                    self.hud.root.after(1, lambda: self.hud._add_system_message(msg, style))
                except Exception:
                    pass

        self._log_handler = HUDHandler(self)
        self._log_handler.setFormatter(logging.Formatter("%(message)s"))
        logging.getLogger().addHandler(self._log_handler)

        self.root.bind("<Escape>", lambda e: self.root.destroy())
        self.root.after(10, self._ensure_front)
        
        self._add_agent_message("Hey, ready when you are.")
        
        # Add usage tips
        self._show_usage_tips()

    # ---------- DRAWING ----------

    def _draw_mic_icon(self, active=False):
        # Handle both canvas and button mic icons
        if hasattr(self, 'mic_canvas'):
            self.mic_canvas.delete("all")
            color = self.color_success if active else self.color_text_muted
            self.mic_canvas.create_oval(3, 3, 23, 23, fill="", outline=color, width=2)
            x_positions = [8, 11, 14, 17, 20]
            heights = [8, 12, 16, 12, 8] if not active else [10, 14, 18, 14, 10]
            for x, h in zip(x_positions, heights):
                y1 = 13 - h // 2
                y2 = 13 + h // 2
                self.mic_canvas.create_line(x, y1, x, y2, fill=color, width=2)
        elif hasattr(self, 'mic_btn'):
            # Update button image
            if active and hasattr(self, 'mic_btn_active_photo'):
                self.mic_btn.config(image=self.mic_btn_active_photo)
            elif not active and hasattr(self, 'mic_btn_inactive_photo'):
                self.mic_btn.config(image=self.mic_btn_inactive_photo)
        
        if active:
            self._voice_running = True
            self._animate_mic_waveform()
        else:
            self._voice_running = False

    def _animate_mic_waveform(self):
        if not self._voice_running:
            return
        try:
            import random
            self.mic_canvas.delete("all")
            color = self.color_success
            self.mic_canvas.create_oval(3, 3, 23, 23, fill="", outline=color, width=2)
            x_positions = [8, 11, 14, 17, 20]
            for x in x_positions:
                h = random.randint(6, 18)
                y1 = 13 - h // 2
                y2 = 13 + h // 2
                self.mic_canvas.create_line(x, y1, x, y2, fill=color, width=2)
            self.root.after(150, self._animate_mic_waveform)
        except Exception:
            pass

    def _add_hover_canvas(self, canvas):
        def on_enter(e):
            items = canvas.find_all()
            if items:
                outer = items[0]
                canvas.itemconfig(outer, outline=self.color_text_primary)

        def on_leave(e):
            color = self.color_success if self._voice_running else self.color_text_muted
            items = canvas.find_all()
            if items:
                outer = items[0]
                canvas.itemconfig(outer, outline=color)

        canvas.bind("<Enter>", on_enter)
        canvas.bind("<Leave>", on_leave)

    # ---------- SCROLLING ----------

    def _bind_mousewheel(self):
        self.root.bind_all("<MouseWheel>", self._on_mousewheel)
        self.root.bind_all("<Button-4>", self._on_mousewheel)
        self.root.bind_all("<Button-5>", self._on_mousewheel)

    def _unbind_mousewheel(self):
        self.root.unbind_all("<MouseWheel>")
        self.root.unbind_all("<Button-4>")
        self.root.unbind_all("<Button-5>")

    def _on_mousewheel(self, event):
        try:
            if getattr(event, "num", None) == 5 or getattr(event, "delta", 0) < 0:
                self.chat_canvas.yview_scroll(3, "units")
            elif getattr(event, "num", None) == 4 or getattr(event, "delta", 0) > 0:
                self.chat_canvas.yview_scroll(-3, "units")
        except Exception:
            pass

    def _on_frame_configure(self, event=None):
        try:
            self.chat_canvas.configure(scrollregion=self.chat_canvas.bbox("all"))
        except Exception:
            pass

    def _on_canvas_configure(self, event):
        try:
            self.chat_canvas.itemconfig(self.canvas_frame, width=event.width)
        except Exception:
            pass

    def _scroll_to_bottom(self):
        try:
            self.root.after_idle(lambda: self.chat_canvas.yview_moveto(1.0))
        except Exception:
            pass
    
    def _show_usage_tips(self):
        """Display usage tips with examples to help users get started"""
        tips = """Quick Start Examples:

Text Mode:
   "Open notepad and write hello world"

Voice Mode:
   Click mic icon, then say:
   "Hey Theta, open notepad and write hello world"
   
Stop: Click pause button (■) to stop any task
"""
        self._add_system_message(tips, "info")

    # ---------- MESSAGES ----------

    def _add_user_message(self, text):
        msg_frame = tk.Frame(self.chat_container, bg=self.color_panel)
        msg_frame.pack(fill="x", padx=4, pady=6)

        bubble_container = tk.Frame(msg_frame, bg=self.color_panel)
        bubble_container.pack(side="right", padx=(8, 0))

        bubble = tk.Frame(bubble_container, bg=self.color_user_bubble, bd=0)
        bubble.pack(side="right")

        msg_label = tk.Label(
            bubble, text=text, bg=self.color_user_bubble, fg="#ffffff",
            font=self.font_sans, wraplength=380, justify="left",
            padx=14, pady=8,
        )
        msg_label.pack()

        time_label = tk.Label(
            msg_frame, text=datetime.now().strftime("%H:%M"),
            bg=self.color_panel, fg=self.color_text_soft,
            font=self.font_sans_sm,
        )
        time_label.pack(side="right", padx=(0, 2))

        self._scroll_to_bottom()

    def _add_agent_message(self, text):
        msg_frame = tk.Frame(self.chat_container, bg=self.color_panel)
        msg_frame.pack(fill="x", padx=4, pady=6)

        bubble_container = tk.Frame(msg_frame, bg=self.color_panel)
        bubble_container.pack(side="left", padx=(0, 8))

        bubble = tk.Frame(bubble_container, bg=self.color_agent_bubble, bd=0)
        bubble.pack(side="left")

        msg_label = tk.Label(
            bubble, text=text, bg=self.color_agent_bubble,
            fg=self.color_text_primary, font=self.font_sans,
            wraplength=380, justify="left", padx=14, pady=8,
        )
        msg_label.pack()

        time_label = tk.Label(
            msg_frame, text=datetime.now().strftime("%H:%M"),
            bg=self.color_panel, fg=self.color_text_soft,
            font=self.font_sans_sm,
        )
        time_label.pack(side="left", padx=(10, 0))

        self._scroll_to_bottom()

    def _add_system_message(self, text, style="info"):
        color = self.color_text_soft
        if style == "error":
            color = self.color_error
        elif style == "warning":
            color = self.color_warning
        elif style == "success":
            color = self.color_success

        msg_frame = tk.Frame(self.chat_container, bg=self.color_panel)
        msg_frame.pack(fill="x", padx=16, pady=3)

        msg_label = tk.Label(
            msg_frame, text=f"• {text}", bg=self.color_panel,
            fg=color, font=(self.font_sans[0], 9, "italic"),
            wraplength=400, justify="left",
        )
        msg_label.pack(anchor="w")

        self._scroll_to_bottom()

    def _show_typing_indicator(self):
        if self.typing_frame:
            return
        self.typing_frame = tk.Frame(self.chat_container, bg=self.color_panel)
        self.typing_frame.pack(fill="x", padx=4, pady=6)

        bubble_container = tk.Frame(self.typing_frame, bg=self.color_panel)
        bubble_container.pack(side="left", padx=(0, 80))

        bubble = tk.Frame(bubble_container, bg=self.color_agent_bubble, bd=0)
        bubble.pack(side="left")

        self.state_label = tk.Label(
            bubble, text="starting...", bg=self.color_agent_bubble,
            fg=self.color_text_soft,
            font=(self.font_sans[0], 10, "italic"), padx=14, pady=8,
        )
        self.state_label.pack()

        self._animate_typing(self.state_label, 0)
        self._scroll_to_bottom()

    def _animate_typing(self, label, step):
        try:
            if not self.typing_frame:
                return
            # Show current state with animated dots
            state_text = self.current_state or "processing"
            dots = "." * ((step % 3) + 1)
            label.config(text=f"{state_text}{dots}")
            self.root.after(500, lambda: self._animate_typing(label, step + 1))
        except Exception:
            pass

    def _hide_typing_indicator(self):
        if self.typing_frame:
            self.typing_frame.destroy()
            self.typing_frame = None
            self.state_label = None
        # Keep reasoning visible for a bit longer so user can read it
        # Will be hidden when next task starts
    
    def _on_agent_state_change(self, state: str):
        """Called when agent state changes"""
        state_labels = {
            "perceiving": "Perceiving",
            "planning": "Planning",
            "executing": "Executing",
            "reasoning": "Reasoning",
            "waiting_permission": "Permission",
            "paused": "⏸  Paused",
            "error": "❌ Error",
            "completed": "✓ Complete"
        }
        self.current_state = state_labels.get(state, state.title())
        # Update label if it exists
        if self.state_label and self.typing_frame:
            try:
                self.state_label.config(text=self.current_state)
            except Exception:
                pass
        
        # Start or stop polling for reasoning updates
        if state in ("planning", "executing"):
            self._start_reasoning_poll()
        else:
            self._stop_reasoning_poll()
    
    def _start_reasoning_poll(self):
        """Start polling for reasoning updates"""
        if self.reasoning_poll_id:
            return  # Already polling
        self._poll_reasoning()
    
    def _stop_reasoning_poll(self):
        """Stop polling for reasoning updates"""
        if self.reasoning_poll_id:
            self.root.after_cancel(self.reasoning_poll_id)
            self.reasoning_poll_id = None
    
    def _poll_reasoning(self):
        """Poll for new reasoning and update if changed"""
        try:
            if self._task_running and self.agent_runner:
                reasoning = self.agent_runner.get_reasoning()
                # Update if reasoning is different from what we last showed
                if reasoning and reasoning.strip() and reasoning != self.last_reasoning:
                    self.last_reasoning = reasoning
                    self._update_reasoning(reasoning)
        except Exception:
            pass
        
        # Schedule next poll if still running
        if self._task_running:
            self.reasoning_poll_id = self.root.after(200, self._poll_reasoning)

    def _update_reasoning(self, reasoning_text: str):
        """Update or create reasoning section"""
        if not reasoning_text or not reasoning_text.strip():
            return
        
        # Remove old reasoning if exists
        if self.reasoning_frame:
            self.reasoning_frame.destroy()
            self.reasoning_frame = None
        
        # Create collapsible reasoning section
        self.reasoning_frame = tk.Frame(self.chat_container, bg=self.color_panel)
        self.reasoning_frame.pack(fill="x", padx=4, pady=6)
        
        # Header with collapse button
        header = tk.Frame(self.reasoning_frame, bg=self.color_panel, cursor="hand2")
        header.pack(fill="x")
        
        # Collapse/expand indicator (start COLLAPSED)
        toggle_var = tk.StringVar(value="▶")
        collapse_btn = tk.Label(
            header, textvariable=toggle_var, bg=self.color_panel,
            fg=self.color_accent, font=self.font_sans_sm, width=2
        )
        collapse_btn.pack(side="left", padx=(4, 0))
        
        # Reasoning title
        title = tk.Label(
            header, text="thinking:", bg=self.color_panel,
            fg=self.color_accent, font=(self.font_sans[0], 9)
        )
        title.pack(side="left", padx=4)
        
        # Content frame (collapsible) - INITIALLY HIDDEN
        content_frame = tk.Frame(self.reasoning_frame, bg=self.color_panel)
        # Don't pack yet - keep collapsed by default
        
        # Reasoning text
        reasoning_label = tk.Label(
            content_frame, text=reasoning_text, bg=self.color_panel,
            fg=self.color_text_soft, font=self.font_sans_sm,
            wraplength=380, justify="left"
        )
        reasoning_label.pack(anchor="w")
        
        # Toggle function
        is_expanded = [False]  # Start collapsed
        
        def toggle_reasoning(e=None):
            if is_expanded[0]:
                # Collapse
                content_frame.pack_forget()
                toggle_var.set("▶")
                is_expanded[0] = False
            else:
                # Expand
                content_frame.pack(fill="x", padx=12, pady=(0, 6))
                toggle_var.set("▼")
                is_expanded[0] = True
            self._scroll_to_bottom()
        
        # Bind click to both button and title
        collapse_btn.bind("<Button-1>", toggle_reasoning)
        title.bind("<Button-1>", toggle_reasoning)
        header.bind("<Button-1>", toggle_reasoning)
        
        self._scroll_to_bottom()
    
    def _hide_reasoning(self):
        """Hide reasoning section"""
        self._stop_reasoning_poll()
        self.last_reasoning = None
        if self.reasoning_frame:
            self.reasoning_frame.destroy()
            self.reasoning_frame = None
    
    # Add this NEW method to overlay.py after _hide_reasoning method

    def show_permission_dialog(self, action_description: str, callback):
        """Show permission approval dialog in overlay"""
        # Pause any ongoing animations
        if self.typing_frame:
            self._hide_typing_indicator()
        
        # Create permission dialog frame
        dialog_frame = tk.Frame(self.chat_container, bg=self.color_panel)
        dialog_frame.pack(fill="x", padx=16, pady=10)
        
        # Warning header with orange background
        header = tk.Frame(dialog_frame, bg="#f59e0b", bd=0)
        header.pack(fill="x", pady=(0, 8))
        
        header_label = tk.Label(
            header, text="⚠️  PERMISSION REQUIRED", 
            bg="#f59e0b", fg="#000000",
            font=(self.font_sans[0], 11, "bold"),
            padx=12, pady=8
        )
        header_label.pack()
        
        # Action description
        desc_label = tk.Label(
            dialog_frame, text=action_description,
            bg=self.color_panel, fg=self.color_text_primary,
            font=self.font_sans, wraplength=450, justify="left",
            padx=12, pady=8
        )
        desc_label.pack(fill="x")
        
        # Button container
        button_frame = tk.Frame(dialog_frame, bg=self.color_panel)
        button_frame.pack(fill="x", padx=12, pady=(8, 12))
        
        def on_approve():
            dialog_frame.destroy()
            self._add_system_message("✓ Action approved by user", "success")
            callback(True)
            self._scroll_to_bottom()
        
        def on_reject():
            dialog_frame.destroy()
            self._add_system_message("✗ Action rejected by user", "warning")
            callback(False)
            self._scroll_to_bottom()
        
        # Approve button (green)
        approve_btn = tk.Button(
            button_frame, text="✓ Approve", command=on_approve,
            bg="#22c55e", fg="#ffffff", bd=0, relief="flat",
            font=(self.font_sans[0], 10, "bold"), cursor="hand2",
            padx=20, pady=10
        )
        approve_btn.pack(side="left", padx=(0, 8))
        
        # Reject button (red)
        reject_btn = tk.Button(
            button_frame, text="✗ Reject", command=on_reject,
            bg="#ef4444", fg="#ffffff", bd=0, relief="flat",
            font=(self.font_sans[0], 10, "bold"), cursor="hand2",
            padx=20, pady=10
        )
        reject_btn.pack(side="left")
        
        # Hover effects for buttons
        def on_approve_enter(e):
            approve_btn.config(bg="#16a34a")
        
        def on_approve_leave(e):
            approve_btn.config(bg="#22c55e")
        
        def on_reject_enter(e):
            reject_btn.config(bg="#dc2626")
        
        def on_reject_leave(e):
            reject_btn.config(bg="#ef4444")
        
        approve_btn.bind("<Enter>", on_approve_enter)
        approve_btn.bind("<Leave>", on_approve_leave)
        reject_btn.bind("<Enter>", on_reject_enter)
        reject_btn.bind("<Leave>", on_reject_leave)
        
        self._scroll_to_bottom()


    # ---------- PLACEHOLDER / ENTRY ----------

    def _clear_placeholder(self, event=None):
        if self.entry.get() == self._placeholder:
            self.entry.delete(0, "end")
            self.entry.configure(fg=self.color_text_primary)

    def _clear_placeholder_on_key(self, event=None):
        if self.entry.get() == self._placeholder:
            self.entry.delete(0, "end")
            self.entry.configure(fg=self.color_text_primary)

    def _restore_placeholder(self, event=None):
        if not self.entry.get().strip():
            self.entry.insert(0, self._placeholder)
            self.entry.configure(fg=self.color_text_muted)
            self._set_send_enabled(False)

    def _on_entry_change(self, event=None):
        if self._task_running:
            return
        text = self.entry.get()
        enabled = bool(text.strip()) and text != self._placeholder
        self._set_send_enabled(enabled)

    def _set_send_enabled(self, enabled: bool):
        if enabled and not self._task_running:
            self.send_btn.config(state="normal", fg=self.color_text_soft, bg="#111827", cursor="hand2")
        else:
            self.send_btn.config(state="disabled", fg=self.color_text_muted, bg="#050816", cursor="arrow")

    # ---------- SEND / STOP ----------

    def _set_running_send_button(self):
        # When task is running, hide send button and show pause button
        if hasattr(self, 'send_photo'):
            # Using image buttons
            self.send_btn.pack_forget()  # Hide send button
            if hasattr(self, 'pause_btn') and self.pause_btn:
                self.pause_btn.pack(side="right", padx=8, pady=6)  # Show pause button
        else:
            # Fallback to text button
            self.send_btn.config(text="■", bg="#06b6d4", fg="#020617", state="normal", cursor="hand2", command=self._on_stop_button)

    def _set_idle_send_button(self):
        # When idle, show send button and hide pause button
        if hasattr(self, 'send_photo'):
            # Using image buttons
            if hasattr(self, 'pause_btn') and self.pause_btn:
                self.pause_btn.pack_forget()  # Hide pause button
            self.send_btn.pack(side="right", padx=8, pady=6)  # Show send button
        else:
            # Fallback to text button
            self.send_btn.config(text="↑", bg="#111827", fg=self.color_text_soft, command=self._on_send)
        self._on_entry_change()

    def _on_stop_button(self):
        """Called when stop button is clicked"""
        if self._task_running:
            if self.agent_runner and self.agent_runner.cancel_current():
                self._hide_typing_indicator()
                self._add_system_message("Task stopped", "warning")
            self._task_running = False
            self._set_idle_send_button()
            self.status_label.config(text="Ready", fg=self.color_success)
    
    def _on_send_or_stop(self, event=None):
        # Only allow Enter to send, not to stop
        # Stopping is only allowed via the stop button
        if self._task_running:
            return "break"
        else:
            return self._on_send(event)

    def _on_send(self, event=None):
        if self._task_running:
            return "break"
        text = self.entry.get().strip()
        if not text or text == self._placeholder:
            return "break"

        self._add_user_message(text)
        self.entry.delete(0, "end")
        self._set_send_enabled(False)
        self._hide_reasoning()  # Clear previous reasoning
        self._show_typing_indicator()

        if self.agent_runner:
            # Set up state callback BEFORE submitting task
            self.agent_runner.set_state_callback(self._on_agent_state_change)
            self.status_label.config(text="Starting…", fg=self.color_accent)
            self._task_running = True
            self._set_running_send_button()

            try:
                fut = self.agent_runner.submit(text)
                self.current_future = fut
            except Exception as e:
                self._task_running = False
                self._hide_typing_indicator()
                self._add_system_message(f"Error: {e}", "error")
                self.status_label.config(text="Ready", fg=self.color_success)
                self._set_idle_send_button()
                return "break"

            def done(f):
                self._hide_typing_indicator()
                try:
                    res = f.result()
                    # Check if result is a dict with success/error info
                    if isinstance(res, dict):
                        if res.get("success"):
                            msg = "✓ Task completed successfully"
                            self.root.after(1, lambda: self._add_agent_message(msg))
                        else:
                            error = res.get("error", "Unknown error")
                            self.root.after(1, lambda: self._add_system_message(f"Task failed: {error}", "error"))
                    else:
                        # Show result as agent message if it's a string
                        res_str = str(res).strip()
                        if res_str and res_str != "{}":
                            self.root.after(1, lambda: self._add_agent_message(res_str))
                except Exception as e:
                    self.root.after(1, lambda: self._add_system_message(f"Error: {e}", "error"))
                finally:
                    self._task_running = False
                    self.root.after(1, lambda: self.status_label.config(text="Ready", fg=self.color_success))
                    self.root.after(1, self._set_idle_send_button)

            fut.add_done_callback(done)
        else:
            self._hide_typing_indicator()
            self._add_system_message("Agent not running", "warning")

        return "break"

    # ---------- VOICE ----------

    def _toggle_voice(self):
        if self._task_running:
            self._add_system_message("Cannot start voice while task is running", "warning")
            return
        if not self.agent_runner:
            self._add_system_message("Voice unavailable", "error")
            return
        if not self._voice_running:
            def cb(cmd):
                self.root.after(1, lambda: self._handle_voice_cmd(cmd))
            try:
                self.agent_runner.start_voice(callback=cb)
                self._voice_running = True
                self._draw_mic_icon(True)
                self._add_system_message("Voice listening", "success")
                self.status_label.config(text="Listening", fg=self.color_success)
            except Exception as e:
                self._add_system_message(f"Voice error: {e}", "error")
        else:
            try:
                self.agent_runner.stop_voice()
                self._voice_running = False
                self._draw_mic_icon(False)
                self._add_system_message("Voice stopped", "info")
                self.status_label.config(text="Ready", fg=self.color_success)
            except Exception as e:
                self._add_system_message(f"Error: {e}", "error")

    def _handle_voice_cmd(self, cmd):
        if self._task_running:
            self._add_system_message("Ignoring voice input while a task is running", "warning")
            return
        try:
            text = cmd.text if hasattr(cmd, "text") else str(cmd)
            text = text.strip()
            if not text:
                return
            self._add_user_message(f"{text}")
            self._set_send_enabled(False)
            self._hide_reasoning()  # Clear previous reasoning
            self._show_typing_indicator()
            if self.agent_runner:
                # Set up state callback BEFORE submitting task
                self.agent_runner.set_state_callback(self._on_agent_state_change)
                self._task_running = True
                self._set_running_send_button()
                self.status_label.config(text="Starting…", fg=self.color_accent)
                
                fut = self.agent_runner.submit(text)
                self.current_future = fut

                def done(f):
                    self._hide_typing_indicator()
                    try:
                        res = f.result()
                        # Check if result is a dict with success/error info
                        if isinstance(res, dict):
                            if res.get("success"):
                                msg = "✓ Task completed successfully"
                                self.root.after(1, lambda: self._add_agent_message(msg))
                            else:
                                error = res.get("error", "Unknown error")
                                self.root.after(1, lambda: self._add_system_message(f"Task failed: {error}", "error"))
                        else:
                            # Show result as agent message if it's a string
                            res_str = str(res).strip()
                            if res_str and res_str != "{}":
                                self.root.after(1, lambda: self._add_agent_message(res_str))
                    except Exception as e:
                        self.root.after(1, lambda: self._add_system_message(f"Error: {e}", "error"))
                    finally:
                        self._task_running = False
                        self.root.after(1, lambda: self.status_label.config(text="Ready", fg=self.color_success))
                        self.root.after(1, self._set_idle_send_button)

                fut.add_done_callback(done)
        except Exception as e:
            self._add_system_message(f"Voice error: {e}", "error")

    # ---------- WINDOW / MISC ----------

    def _start_drag(self, event):
        self._drag_start_x = event.x
        self._drag_start_y = event.y

    def _on_drag(self, event):
        x = self.root.winfo_x() + event.x - self._drag_start_x
        y = self.root.winfo_y() + event.y - self._drag_start_y
        self.root.geometry(f"+{x}+{y}")

    def _ensure_front(self):
        try:
            self.root.lift()
            self.root.attributes("-topmost", True)
        except Exception:
            pass

    def run(self):
        self._ensure_front()

        def _on_close():
            try:
                if self.agent_runner:
                    try:
                        self.agent_runner.stop_voice()
                    except Exception:
                        pass
                    try:
                        self.agent_runner.cancel_current()
                    except Exception:
                        pass
                    try:
                        self.agent_runner.shutdown()
                    except Exception:
                        pass
            finally:
                self.root.destroy()

        self.root.protocol("WM_DELETE_WINDOW", _on_close)
        self.root.mainloop()


if __name__ == "__main__":
    hud = OverlayHUD(title="Theta Ai")
    hud.run()
