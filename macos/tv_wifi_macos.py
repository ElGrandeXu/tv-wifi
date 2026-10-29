#!/usr/bin/env python3
"""Interface Mac native Tk : sélection de TV, écran, connexion et arrêt."""
import fcntl
from pathlib import Path
import queue
import signal
import sys
import threading

import dlna
from mac_backend import Controller, list_screens, request_screen_permission


def main():
    if sys.platform != 'darwin':
        print('Ce lanceur est réservé à macOS. La version Linux reste indépendante.')
        return 1
    import tkinter as tk
    from tkinter import ttk

    dlna.PREFS.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    lock = (dlna.PREFS.parent/'application.lock').open('a')
    try:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return 0

    root = tk.Tk()
    root.title('TV Wi-Fi')
    root.minsize(540, 365)
    root.resizable(True, False)
    content = ttk.Frame(root, padding=22)
    content.grid(sticky='nsew')
    root.columnconfigure(0, weight=1)
    content.columnconfigure(0, weight=1)
    ttk.Label(content, text='Votre écran sur la TV', font=('Helvetica', 18, 'bold')).grid(
        row=0, column=0, columnspan=2, sticky='w', pady=(0, 8))
    ttk.Label(content, text='Full HD 1080p · 30 images/s · Sans son').grid(
        row=1, column=0, columnspan=2, sticky='w', pady=(0, 16))
    tv_choice = ttk.Combobox(content, state='readonly', width=37)
    tv_choice.grid(row=2, column=0, sticky='ew', padx=(0, 8))
    refresh = ttk.Button(content, text='Rechercher les TV')
    refresh.grid(row=2, column=1)
    prefs = dlna.load_preferences()
    ip = tk.StringVar(value=str(prefs.get('last_ip', '')))
    ttk.Label(content, text='Ou adresse IP de la TV :').grid(row=3, column=0, sticky='w', pady=(12, 3))
    entry = ttk.Entry(content, textvariable=ip)
    entry.grid(row=4, column=0, columnspan=2, sticky='ew')
    ttk.Label(content, text='Écran à partager :').grid(row=5, column=0, sticky='w', pady=(12, 3))
    screen_choice = ttk.Combobox(content, state='readonly')
    screen_choice.grid(row=6, column=0, columnspan=2, sticky='ew')
    enabled = tk.BooleanVar(value=False)
    toggle = ttk.Checkbutton(content, text='Partager mon écran', variable=enabled)
    toggle.grid(row=7, column=0, columnspan=2, sticky='w', pady=15)
    status = tk.StringVar(value='Recherche des TV et des écrans…')
    ttk.Label(content, textvariable=status, wraplength=495).grid(
        row=8, column=0, columnspan=2, sticky='w')
    ttk.Label(content, text='Même réseau que la TV · Plusieurs secondes de décalage possibles.\n'
              'Tout l’écran est partagé. Fermer la fenêtre coupe la diffusion.',
              foreground='#666666', wraplength=495).grid(
        row=9, column=0, columnspan=2, sticky='w', pady=(14, 0))

    controller = Controller()
    messages = queue.Queue()
    known, found, screens = [], [], []
    closing = False
    searching = False
    search_cancel = threading.Event()
    try:
        remembered = dlna.TV(**prefs['last_tv'])
        dlna.checked_url(remembered.location, remembered.ip)
        known.append(remembered)
    except (KeyError, TypeError, dlna.TVError):
        pass

    def update_controls():
        idle = controller.state == 'idle'
        entry.configure(state='normal' if idle else 'disabled')
        tv_choice.configure(state='readonly' if idle else 'disabled')
        screen_choice.configure(state='readonly' if idle else 'disabled')
        refresh.configure(state='normal' if idle and not searching else 'disabled')
        toggle.configure(state='disabled' if controller.state == 'disconnecting' or (idle and not screens) else 'normal')

    def choose_tv(event=None):
        index = tv_choice.current()
        if 0 <= index < len(found):
            ip.set(found[index].ip)
    tv_choice.bind('<<ComboboxSelected>>', choose_tv)

    def search():
        nonlocal searching
        if searching or closing:
            return
        searching = True
        refresh.configure(text='Recherche…')
        update_controls()
        def worker():
            try:
                messages.put(('tvs', dlna.discover(cancel=search_cancel)))
            except Exception as error:
                messages.put(('error', str(error)))
                messages.put(('tvs', []))
        threading.Thread(target=worker, daemon=True).start()
    refresh.configure(command=search)

    def screen_search():
        try:
            messages.put(('screens', list_screens()))
        except Exception as error:
            messages.put(('screen_error', str(error)))

    def switched():
        if not enabled.get():
            controller.disconnect()
            update_controls()
            return
        if controller.state != 'idle':
            return
        try:
            dlna.parse_ip(ip.get())
            index = screen_choice.current()
            if not 0 <= index < len(screens):
                raise dlna.TVError('Choisissez l’écran à partager.')
            if not request_screen_permission():
                raise dlna.TVError('Autorisez l’enregistrement de l’écran dans les réglages du Mac, '
                                   'puis relancez TV Wi-Fi. Aucun son n’est demandé.')
            controller.connect(ip.get(), screens[index][0], list(known))
            update_controls()
        except Exception as error:
            enabled.set(False)
            status.set(str(error))
    toggle.configure(command=switched)

    def close():
        nonlocal closing
        closing = True
        search_cancel.set()
        enabled.set(False)
        controller.disconnect()
        status.set('Arrêt de la diffusion…')

    root.protocol('WM_DELETE_WINDOW', close)
    root.createcommand('tk::mac::Quit', close)
    root.createcommand('tk::mac::ReopenApplication', root.lift)
    signal.signal(signal.SIGTERM, lambda *_: close())
    signal.signal(signal.SIGINT, lambda *_: close())

    def poll():
        nonlocal searching, found, known, screens
        try:
            while True:
                event = messages.get_nowait()
                if event[0] == 'tvs':
                    searching = False
                    found = event[1]
                    known = list({tv.ip: tv for tv in known + found}.values())
                    tv_choice.configure(values=[f'{tv.name} — {tv.ip}' for tv in found])
                    refresh.configure(text='Rechercher les TV')
                    if controller.state == 'idle' and screens:
                        status.set(f'{len(found)} TV disponible(s). Choisissez celle de votre salle.'
                                   if found else 'Aucune TV détectée. Essayez son IP ou vérifiez le réseau local.')
                elif event[0] == 'screens':
                    screens = event[1]
                    screen_choice.configure(values=[label for name, label in screens])
                    if screens:
                        screen_choice.current(0)
                        if controller.state == 'idle' and not searching:
                            status.set(f'{len(found)} TV disponible(s). Choisissez celle de votre salle.'
                                       if found else 'Aucune TV détectée. Essayez son IP ou vérifiez le réseau local.')
                else:
                    status.set(event[1])
                update_controls()
        except queue.Empty:
            pass
        try:
            while True:
                _, state, message = controller.events.get_nowait()
                status.set(message)
                enabled.set(state in {'connecting', 'connected'})
                update_controls()
        except queue.Empty:
            pass
        controller.monitor()
        if closing and controller.state == 'idle':
            root.destroy()
            return
        root.after(100, poll)

    search()
    threading.Thread(target=screen_search, daemon=True).start()
    root.after(100, poll)
    root.mainloop()
    lock.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
