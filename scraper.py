def revisar_ofertas(filtro_objetivo="TODOS"):
    res = supabase.table("radares").select("*").execute()
    if not res or not res.data: return "Sin radares activos."
    
    total = 0
    alertas_enviadas = 0
    lista_html_streamlit = []
    
    mapa_emojis = {
        "PERFUMES": "🧪", "ZAPATILLAS": "👟", "MEDIAS": "🧦", "POLOS": "👕", 
        "CASACAS": "🧥", "SHORTS": "🩳", "BUZOS": "👖", "AUDIFONOS": "🎧", 
        "TV": "📺", "PARLANTE": "🔊", "BARRA DE SONIDO": "🎵", "CELULAR": "📱", 
        "PC": "💻", "REFRIGERADORA": "❄️", "LAVADORA": "🧺", 
        "ELECTRODOMESTICOS": "🔌", "CAMA": "🛏️", "OTROS": "📦"
    }
    enviados_en_este_clic = set()
    fecha_hoy = datetime.now().strftime("%Y-%m-%d")
    
    target = str(filtro_objetivo).strip().upper()
    
    for item in res.data:
        ident = item['identificador'].upper()
        url_low = item['url'].lower()
        
        # 🧠 DICCIONARIO EXPANDIDO: Captura audífonos, auriculares o enlaces 'wireless/tws'
        if any(k in ident for k in ["AUDIFONO", "AURICULAR", "FONO"]) or any(k in url_low for k in ["wireless", "tws", "headphone", "audio-oars"]): 
            grupo = "AUDIFONOS"
        elif "BARRA" in ident or "SOUNDBAR" in ident or "barra" in url_low: 
            grupo = "BARRA DE SONIDO"
        elif "PARLANTE" in ident or "ALTAVOZ" in ident or "parlante" in url_low: 
            grupo = "PARLANTE"
        elif "TV" in ident or "TELEVISOR" in ident or "smart-tv" in url_low: 
            grupo = "TV"
        elif "CELULAR" in ident or "TELEFONO" in ident or "smartphone" in url_low: 
            grupo = "CELULAR"
        elif "PC" in ident or "LAPTOP" in ident: 
            grupo = "PC"
        elif "REFRIGERADORA" in ident or "NEVERA" in ident: 
            grupo = "REFRIGERADORA"
        elif "LAVADORA" in ident: 
            grupo = "LAVADORA"
        elif "ELECTRO" in ident or "LICUADORA" in ident: 
            grupo = "ELECTRODOMESTICOS"
        elif "CAMA" in ident or "COLCHON" in ident: 
            grupo = "CAMA"
        elif "PERFUME" in ident: 
            grupo = "PERFUMES"
        elif "ZAPATILLA" in ident: 
            grupo = "ZAPATILLAS"
        elif "MEDIAS" in ident: 
            grupo = "MEDIAS"
        elif "POLO" in ident: 
            grupo = "POLOS"
        elif "CASACA" in ident: 
            grupo = "CASACAS"
        elif "SHORT" in ident: 
            grupo = "SHORTS"
        elif "BUZO" in ident: 
            grupo = "BUZOS"
        else: 
            grupo = "OTROS"
        
        if target != "TODOS" and target != grupo:
            continue
        
        prods = escanear_tienda(item['url'], item['precio_max'])
        for p in prods:
            try:
                nombre_unico = p['nombre'].strip().upper()
                if nombre_unico in enviados_en_este_clic: continue
                enviados_en_este_clic.add(nombre_unico)
                
                lista_html_streamlit.append(p)
                total += 1
                
                ya_alertado = False
                try:
                    check = supabase.table("historial_precios")\
                        .select("id")\
                        .eq("identificador", item['identificador'])\
                        .eq("precio", p['precio'])\
                        .eq("fecha", fecha_hoy)\
                        .execute()
                    if check.data and len(check.data) > 0:
                        ya_alertado = True
                except: pass
                
                supabase.table("historial_precios").insert({
                    "identificador": item['identificador'], "precio": p['precio'], "fecha": fecha_hoy
                }).execute()
                
                if ya_alertado:
                    continue
                
                emoji = mapa_emojis.get(grupo, "🔥")
                text_alerta = f"{emoji} *PRODUCTO EN TU RANGO* {emoji}\n"
                text_alerta += f"━━━━━━━━━━━━━━━━━━━━━\n\n"
                text_alerta += f"📦 *Producto:* `{p['nombre']}`\n"
                text_alerta += f"🏪 *Tienda:* `{ident.split('-')[0]}`\n"
                text_alerta += f"🏷️ *Categoría:* `{grupo}`\n"
                text_alerta += f"💵 *Precio Actual:* `S/. {p['precio']:.2f}`\n"
                text_alerta += f"🎯 *Tu Tope:* `S/. {item['precio_max']:.2f}`\n"
                enviar_telegram(text_alerta, p['link'], p.get('img', ''))
                alertas_enviadas += 1
                time.sleep(0.4)
            except: pass
            
    if len(lista_html_streamlit) > 0:
        try:
            import streamlit as st
            st.write(f"### 🎯 Modelos encontrados en este instante ({len(lista_html_streamlit)}):")
            for prod in lista_html_streamlit:
                with st.container(border=True):
                    col1, col2 = st.columns([2, 8])
                    with col1:
                        if prod.get('img'): st.image(prod['img'], width=120)
                        else: st.write("📷 _Sin Foto_")
                    with col2:
                        st.markdown(f"#### `{prod['nombre']}`")
                        
                        p_oferta = prod['precio']
                        p_regular = prod.get('precio_regular', p_oferta)
                        
                        if p_regular > p_oferta:
                            ahorro_soles = p_regular - p_oferta
                            porcentaje = (ahorro_soles / p_regular) * 100
                            st.markdown(f"❌ ~~Precio Regular: S/. {p_regular:.2f}~~")
                            st.markdown(f"💰 **Precio Oferta: S/. {p_oferta:.2f}**")
                            st.markdown(f"🔥 **¡Ahorraste S/. {ahorro_soles:.2f}! ({porcentaje:.0f}% de Descuento)**")
                        else:
                            st.markdown(f"💰 **Precio Actual: S/. {p_oferta:.2f}**")
                            st.caption("ℹ️ _Precio de etiqueta original o sin descuento de lista reportado._")
                            
                        st.markdown(f"🔗 [🌐 IR A COMPRAR DIRECTO EN LA TIENDA]({prod['link']})")
        except: pass

    return f"Éxito. Modelos únicos: {total}. Alertas enviadas a Telegram: {alertas_enviadas}."
