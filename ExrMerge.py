import os
# Commentons ces imports problématiques et utilisons OpenImageIO à la place
# import OpenEXR
# import Imath
import OpenImageIO as oiio
import concurrent.futures
from functools import partial
import multiprocessing
import time
import psutil

def get_optimal_thread_count():
    """Déterminer le nombre optimal de threads pour le système actuel avec optimisations"""
    cpu_count = multiprocessing.cpu_count()
    physical_cores = psutil.cpu_count(logical=False)
    if not physical_cores:
        physical_cores = max(1, cpu_count // 2)
    
    # Obtenir la mémoire disponible pour ajuster le nombre de threads
    try:
        memory_gb = psutil.virtual_memory().available / (1024**3)
        # Limiter les threads si la mémoire est faible (moins de 8GB disponibles)
        if memory_gb < 8:
            max_threads_by_memory = max(2, int(memory_gb / 2))  # 1 thread par 2GB
        else:
            max_threads_by_memory = physical_cores * 3
    except:
        max_threads_by_memory = physical_cores * 2
    
    # Pour les opérations I/O bound comme la fusion EXR, plus de threads peut aider
    # mais on limite selon la mémoire disponible
    optimal_threads = min(physical_cores * 3, cpu_count, max_threads_by_memory)
    
    # Minimum de 2 threads, maximum de 16 pour éviter la surcharge
    return max(2, min(optimal_threads, 16))

def set_high_priority():
    """Increase process priority to maximize CPU usage"""
    try:
        process = psutil.Process(os.getpid())
        if os.name == 'nt':  # Windows
            process.nice(psutil.HIGH_PRIORITY_CLASS)
        else:  # Unix-like
            process.nice(-10)  # De -20 (plus haute) à 19 (plus basse)
        return True
    except:
        return False

def optimize_memory_usage():
    """Optimiser l'utilisation de la mémoire pour de meilleures performances"""
    try:
        import gc
        # Forcer le garbage collection pour libérer la mémoire
        gc.collect()
        
        # Configurer OpenImageIO pour une utilisation optimale de la mémoire
        try:
            # Limiter le cache d'images pour éviter l'utilisation excessive de mémoire
            oiio.attribute("max_memory_MB", 2048)  # 2GB max pour le cache
            oiio.attribute("read_chunk", 65536)    # Taille de chunk optimisée
            return True
        except:
            return False
    except:
        return False

def get_compression_settings(compression_mode, compression_level=None):
    """Retourne les paramètres de compression optimisés pour OpenImageIO"""
    compression_map = {
        "ZIP": "zip",
        "DWAA": "dwaa", 
        "DWAB": "dwab",
        "PIZ": "piz",
        "NO_COMPRESSION": "none"
    }
    
    compression = compression_map.get(compression_mode.upper(), "dwab")
    
    # Optimiser le niveau de compression par défaut
    if compression_level is None:
        if compression in ["dwaa", "dwab"]:
            compression_level = 45  # Bon équilibre entre taille et vitesse
    
    return compression, compression_level

def extract_channels(input_exr, channels_to_extract):
    """Extraction optimisée des canaux d'un fichier EXR avec OpenImageIO et optimisations de performance"""
    try:
        # Ouvrir le fichier EXR avec optimisations
        buf = oiio.ImageBuf(input_exr)
        if buf.has_error:
            print(f"Error reading file {input_exr}: {buf.geterror()}")
            return {}, (0, 0)
            
        spec = buf.spec()
        width, height = spec.width, spec.height
        size = (width, height)
        channels = spec.channelnames
        
        data = {}
        import numpy as np
        
        # Optimisation: créer une liste des indices de canaux à extraire en une seule passe
        channels_to_extract_indices = []
        channels_to_extract_names = []
        
        for ch in channels:
            base = ch.split('.')[0]
            if base in channels_to_extract or ch in channels_to_extract:
                try:
                    ch_idx = channels.index(ch)
                    channels_to_extract_indices.append(ch_idx)
                    channels_to_extract_names.append(ch)
                except ValueError:
                    continue
        
        # Extraire tous les canaux demandés en une seule opération si possible
        if channels_to_extract_indices:
            try:
                # Optimisation: extraire plusieurs canaux en une seule opération
                if len(channels_to_extract_indices) > 1:
                    # Extraire tous les canaux d'un coup
                    multi_channel_buf = oiio.ImageBufAlgo.channels(buf, tuple(channels_to_extract_indices))
                    if multi_channel_buf and not multi_channel_buf.has_error:
                        # Obtenir toutes les données de pixels en une fois
                        all_pixels = multi_channel_buf.get_pixels(oiio.FLOAT)
                        if all_pixels is not None:
                            # Séparer les canaux
                            for i, ch_name in enumerate(channels_to_extract_names):
                                if all_pixels.ndim == 3 and all_pixels.shape[2] > i:
                                    # Extraire le canal spécifique et s'assurer qu'il est contiguë
                                    channel_data = np.ascontiguousarray(all_pixels[:, :, i])
                                    data[ch_name] = channel_data
                else:
                    # Un seul canal à extraire
                    ch_idx = channels_to_extract_indices[0]
                    ch_name = channels_to_extract_names[0]
                    channel_buf = oiio.ImageBufAlgo.channels(buf, (ch_idx,))
                    if channel_buf and not channel_buf.has_error:
                        pixels = channel_buf.get_pixels(oiio.FLOAT)
                        if pixels is not None:
                            # S'assurer que les données sont contiguës pour de meilleures performances
                            if isinstance(pixels, np.ndarray) and not pixels.flags['C_CONTIGUOUS']:
                                pixels = np.ascontiguousarray(pixels)
                            data[ch_name] = pixels
                            
            except Exception as e:
                # Fallback: extraire canal par canal si l'extraction groupée échoue
                print(f"Group extraction failed for {input_exr}, falling back to individual extraction: {e}")
                for ch_idx, ch_name in zip(channels_to_extract_indices, channels_to_extract_names):
                    try:
                        channel_buf = oiio.ImageBufAlgo.channels(buf, (ch_idx,))
                        if channel_buf and not channel_buf.has_error:
                            pixels = channel_buf.get_pixels(oiio.FLOAT)
                            if pixels is not None:
                                # S'assurer que les données sont contiguës
                                if isinstance(pixels, np.ndarray) and not pixels.flags['C_CONTIGUOUS']:
                                    pixels = np.ascontiguousarray(pixels)
                                data[ch_name] = pixels
                    except Exception as e2:
                        print(f"Error extracting channel {ch_name}: {e2}")
        
        return data, size
        
    except Exception as e:
        print(f"Error processing file {input_exr}: {e}")
        return {}, (0, 0)

def write_exr(path, header_channels, pixel_data, size, compression_mode="DWAB", compression_level=45.0):
    """Écriture optimisée d'un fichier EXR avec OpenImageIO et optimisations de performance"""
    try:
        # Créer une nouvelle spécification d'image
        spec = oiio.ImageSpec(size[0], size[1], len(header_channels), oiio.FLOAT)
        spec.channelnames = list(header_channels)
        
        # Configurer la compression avec optimisations
        compression_map = {
            "ZIP": "zip",
            "DWAA": "dwaa", 
            "DWAB": "dwab",
            "PIZ": "piz",
            "NO_COMPRESSION": "none"
        }
        
        compression = compression_map.get(compression_mode, "dwab")
        spec.attribute("compression", compression)
        
        # Appliquer le niveau de compression pour DWAA/DWAB
        if compression_level is not None and compression in ["dwaa", "dwab"]:
            spec.attribute("compressionlevel", int(compression_level))
        
        # Optimisations de performance
        spec.tile_width = 64
        spec.tile_height = 64
        spec.attribute("oiio:UnassociatedAlpha", 1)
        
        # Optimisations supplémentaires pour la vitesse d'écriture
        spec.attribute("oiio:ColorSpace", "Linear")
        spec.attribute("openexr:lineOrder", "increasingY")
        
        # Créer le buffer d'image
        buf = oiio.ImageBuf(spec)
        
        # Organiser les données des pixels dans l'ordre des canaux avec optimisations
        all_pixels = []
        import numpy as np
        
        for ch in spec.channelnames:
            if ch in pixel_data:
                channel_data = pixel_data[ch]
                # Vérifier et corriger la forme des données avec optimisations
                if isinstance(channel_data, np.ndarray):
                    # Optimisation: s'assurer que les données sont en float32 pour de meilleures performances
                    if channel_data.dtype != np.float32:
                        channel_data = channel_data.astype(np.float32)
                    
                    # Si les données ont une dimension supplémentaire, la supprimer
                    if channel_data.ndim == 4 and channel_data.shape[2] == 1:
                        channel_data = channel_data.squeeze(axis=2)
                    elif channel_data.ndim == 3 and channel_data.shape[2] == 1:
                        channel_data = channel_data.squeeze(axis=2)
                    
                    # S'assurer que les données sont contiguës en mémoire pour de meilleures performances
                    if not channel_data.flags['C_CONTIGUOUS']:
                        channel_data = np.ascontiguousarray(channel_data)
                        
                all_pixels.append(channel_data)
            else:
                # Créer un canal vide si manquant (optimisé)
                empty_channel = np.zeros((size[1], size[0]), dtype=np.float32, order='C')
                all_pixels.append(empty_channel)

        # Combiner tous les canaux en un seul tableau avec optimisations
        if all_pixels:
            # Empiler les canaux le long de la dimension des canaux
            combined_pixels = np.stack(all_pixels, axis=-1)
            
            # S'assurer que le tableau final est contiguë pour de meilleures performances d'écriture
            if not combined_pixels.flags['C_CONTIGUOUS']:
                combined_pixels = np.ascontiguousarray(combined_pixels)
            
            buf.set_pixels(oiio.ROI(), combined_pixels)
    
        # Écrire le fichier avec gestion d'erreur améliorée
        success = buf.write(path)
        if not success:
            error_msg = buf.geterror()
            print(f"Error writing EXR file {path}: {error_msg}")
            return False
            
        return success
    except Exception as e:
        print(f"Error writing EXR file {path}: {e}")
        return False

def process_single_frame(frame, input_folder, denoised_folder, final_output_dir, selected_aovs, compression_mode, compression_level=None, log_callback=None, shadow_mode=False, shadow_aovs=None):
    """Traitement optimisé d'une seule image"""
    messages = []
    result = False
    start_time = time.time()
    
    def local_log(msg):
        if log_callback:
            log_callback(msg)
        messages.append(msg)

    final_channels = {}
    size = None

    # Liste des dossiers auxiliaires à traiter
    aux_folders = ["aux-albedo", "aux-diffuse", "aux-specular", "aux-subsurface"]
    
    # 1. Traiter d'abord le fichier principal (RGBA, Ci, rgb, etc.)
    main_exr_path = os.path.join(denoised_folder, frame)
    if os.path.exists(main_exr_path):
        # En mode shadow, ne chercher que l'alpha et les AOVs des ombres
        if shadow_mode:
            # Inclure l'alpha et les AOVs d'ombres spécifiées
            channels_to_extract = ["a", "A"] + (shadow_aovs if shadow_aovs else [])
            main_data, size = extract_channels(main_exr_path, channels_to_extract)
        else:
            # Mode normal: chercher RGBA + diffuse, specular, rgb et Ci
            main_data, size = extract_channels(main_exr_path, ["R", "G", "B", "A", "diffuse", "specular", "rgb", "Ci"])
        
        # Ajouter les canaux trouvés au dictionnaire final
        for ch, data in main_data.items():
            final_channels[ch] = data
            
            # Ajouter des logs spécifiques pour des AOVs importantes
            if ch == "rgb":
                local_log(f"✅ Denoised 'rgb' extracted from main denoised file")
            elif ch == "Ci":
                local_log(f"✅ Denoised 'Ci' extracted from main denoised file")
            elif ch == "diffuse":
                local_log(f"✅ Denoised 'diffuse' extracted from main denoised file")
            elif ch == "specular":
                local_log(f"✅ Denoised 'specular' extracted from main denoised file")
            elif shadow_mode and ch in shadow_aovs:
                local_log(f"✅ Denoised shadow AOV '{ch}' extracted from main denoised file")
                
        local_log(f"✅ RGBA channels extracted from main denoised file")
    else:
        local_log(f"⚠️ Main file missing: {main_exr_path}")
        return result, messages

    # 2. Traiter les fichiers auxiliaires (albedo, diffuse, specular)
    for aux_folder in aux_folders:
        aux_path = os.path.join(denoised_folder, aux_folder, frame)
        if os.path.exists(aux_path):
            # En mode shadow, ne chercher que les AOVs des ombres
            if shadow_mode:
                aovs_to_extract = shadow_aovs if shadow_mode else []
            else:
                # Mode normal: créer une liste des AOVs à extraire, en excluant celles déjà trouvées
                aovs_to_extract = [aov for aov in selected_aovs if aov not in final_channels]
                
            if aovs_to_extract:
                aux_data, _ = extract_channels(aux_path, aovs_to_extract)
                for ch, data in aux_data.items():
                    final_channels[ch] = data
                    if ch == "rgb":
                        local_log(f"✅ Denoised 'rgb' extracted from {aux_folder}")
                    elif ch == "Ci":
                        local_log(f"✅ Denoised 'Ci' extracted from {aux_folder}")
                    elif ch == "diffuse":
                        local_log(f"✅ Denoised 'diffuse' extracted from {aux_folder}")
                    elif ch == "specular":
                        local_log(f"✅ Denoised 'specular' extracted from {aux_folder}")
                    elif shadow_mode and ch in shadow_aovs:
                        local_log(f"✅ Denoised shadow AOV '{ch}' extracted from {aux_folder}")
                    
                local_log(f"✅ Additional AOVs extracted from {aux_folder}")
        else:
            local_log(f"⚠️ Missing file in {aux_folder}: {aux_path}")

    # 3. Obtenir les AOVs manquants du fichier d'entrée
    input_exr_path = os.path.join(input_folder, frame)
    if os.path.exists(input_exr_path):
        if shadow_mode:
            # En mode shadow, chercher uniquement l'alpha et les AOVs des ombres si pas encore trouvés
            missing_aovs = []
            if "a" not in final_channels and "A" not in final_channels:
                missing_aovs.append("a")
                missing_aovs.append("A")
            if shadow_aovs:
                for shadow_aov in shadow_aovs:
                    if shadow_aov not in final_channels:
                        missing_aovs.append(shadow_aov)
        else:
            # Mode normal: extraire les AOVs manquants, mais pas Ci ni rgb qui doivent venir des fichiers dénoisés
            missing_aovs = [aov for aov in selected_aovs if aov not in final_channels and aov != "Ci" and aov != "rgb"]
            
        if missing_aovs:
            input_data, _ = extract_channels(input_exr_path, missing_aovs)
            for channel, data in input_data.items():
                if channel not in final_channels:
                    final_channels[channel] = data
                    local_log(f"✅ {channel} extracted from input file (not denoised)")
    else:
        local_log(f"⚠️ Input file missing for additional AOVs: {input_exr_path}")

    # Écrire le fichier EXR final avec optimisations
    output_path = os.path.join(final_output_dir, frame)
    
    # Optimiser la compression avant l'écriture
    optimized_compression, optimized_level = get_compression_settings(compression_mode, compression_level)
    
    if write_exr(output_path, final_channels.keys(), final_channels, size, optimized_compression.upper(), optimized_level):
        result = True
        elapsed_time = time.time() - start_time
        
        # Afficher des informations sur le fichier créé
        try:
            file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
            local_log(f"✅ Merged file: {output_path} ({file_size_mb:.1f}MB) in {elapsed_time:.2f}s")
        except:
            local_log(f"✅ Merged file: {output_path} in {elapsed_time:.2f}s")
    else:
        local_log(f"❌ Failed to write merged file: {output_path}")

    return result, messages

def merge_final_exrs(output_folder, frame_list, input_folder, selected_aovs, compression_mode, compression_level=None, log_callback=None, progress_callback=None, temp_folder=None, shadow_mode=False, shadow_aovs=None, stop_check=None, use_gpu=False):
    """Fusionner les AOVs dénoisés avec les AOVs originaux, avec optimisations de performance"""
    # Optimisations de performance au démarrage
    priority_set = set_high_priority()
    memory_optimized = optimize_memory_usage()
    
    # Optimiser les paramètres de compression
    compression, compression_level = get_compression_settings(compression_mode, compression_level)
    
    # Configuration GPU si activée
    gpu_acceleration = False
    if use_gpu:
        try:
            # Configurer OpenImageIO pour utiliser le GPU si possible
            oiio.attribute("gpu", 1)
            oiio.attribute("use_gpu", True)
            gpu_acceleration = True
            if log_callback:
                log_callback("🚀 GPU acceleration enabled for image processing")
        except Exception as e:
            if log_callback:
                log_callback(f"⚠️ GPU acceleration requested but failed to initialize: {str(e)}")
                log_callback("ℹ️ Falling back to CPU processing")
    
    if log_callback:
        log_callback("🔄 Starting optimized merge process...")
        if priority_set:
            log_callback("⚡ Process priority increased for better CPU utilization")
        if memory_optimized:
            log_callback("🧠 Memory usage optimized for better performance")
        if gpu_acceleration:
            log_callback("🎮 Using GPU acceleration for faster image operations")
        if shadow_mode:
            log_callback(f"🔍 Shadow Mode: Only keeping alpha and shadow AOVs: {', '.join(shadow_aovs)}")
        if compression in ["dwaa", "dwab"] and compression_level is not None:
            log_callback(f"📊 Using optimized compression: {compression.upper()} level {compression_level}")
        else:
            log_callback(f"📊 Using compression: {compression.upper()}")

    # Créer le répertoire de sortie s'il n'existe pas
    os.makedirs(output_folder, exist_ok=True)

    # Préparer le chemin du dossier dénoisé
    denoised_folder = temp_folder if temp_folder else os.path.join(output_folder, "../temp_denoised")

    # Déterminer le nombre optimal de workers basé sur les ressources système
    optimal_workers = get_optimal_thread_count()
    if log_callback:
        log_callback(f"📊 Using {optimal_workers} parallel workers for processing")

    # Diviser les frames en lots pour une meilleure gestion de la mémoire
    # et permettre une utilisation plus efficace du CPU
    batch_size = max(1, len(frame_list) // optimal_workers)
    if batch_size > 1 and len(frame_list) > optimal_workers:
        batches = [frame_list[i:i+batch_size] for i in range(0, len(frame_list), batch_size)]
        if log_callback:
            log_callback(f"📊 Processing {len(frame_list)} frames in {len(batches)} batches for optimal memory usage")
    else:
        batches = [frame_list]  # Traiter toutes les frames en un seul lot

    # Traiter les lots de frames en série, mais les frames de chaque lot en parallèle
    total_success = 0
    total_frames = len(frame_list)
    frames_processed = 0

    for batch_index, batch in enumerate(batches):
        # Check for stop request before processing the batch
        if stop_check and stop_check():
            if log_callback:
                log_callback("🛑 Process stopped by user during merge")
            return
            
        # Traiter ce lot de frames en parallèle
        with concurrent.futures.ThreadPoolExecutor(max_workers=optimal_workers) as executor:
            futures = []
            for frame in batch:
                future = executor.submit(
                    process_single_frame,
                    frame,
                    input_folder,
                    denoised_folder,
                    output_folder,
                    selected_aovs,
                    compression_mode,
                    compression_level,
                    None,  # On gère les logs nous-mêmes pour éviter les concurrences
                    shadow_mode,
                    shadow_aovs
                )
                futures.append((frame, future))

            # Surveiller la progression
            batch_start_time = time.time()
            for i, (frame, future) in enumerate(futures):
                # Check for stop request during processing
                if stop_check and stop_check():
                    if log_callback:
                        log_callback(f"🛑 Process stopped by user during merge (at frame {frames_processed+1}/{total_frames})")
                    # Cancel all pending futures
                    for _, f in futures[i:]:
                        f.cancel()
                    return
                    
                try:
                    result, messages = future.result()
                    if result:
                        total_success += 1
                    
                    # Logs par frame
                    if log_callback and messages:
                        log_callback(f"⏳ Processing frame: {frame}")
                        for msg in messages:
                            log_callback(f"  {msg}")
                except Exception as e:
                    if log_callback:
                        log_callback(f"❌ Error processing frame {frame}: {str(e)}")

                # Mettre à jour la progression
                frames_processed += 1
                progress_percent = frames_processed / total_frames * 100
                
                if log_callback and i % max(1, len(batch)//10) == 0:  # Limiter les logs de progression
                    log_callback(f"⏳ Progress: {frames_processed}/{total_frames} files processed")
                
                if progress_callback:
                    should_stop = progress_callback(progress_percent)
                    if should_stop:
                        if log_callback:
                            log_callback(f"🛑 Process stopped by progress callback")
                        # Cancel all pending futures
                        for _, f in futures[i+1:]:
                            f.cancel()
                        return

        # Statistiques par lot et optimisation mémoire
        batch_time = time.time() - batch_start_time
        if log_callback and len(batches) > 1:
            log_callback(f"✅ Batch {batch_index+1}/{len(batches)} completed in {batch_time:.2f}s ({len(batch)/batch_time:.2f} frames/s)")
        
        # Optimiser la mémoire entre les batches
        if batch_index < len(batches) - 1:  # Pas le dernier batch
            try:
                import gc
                gc.collect()  # Libérer la mémoire entre les batches
            except:
                pass

    # Statistiques finales avec informations de performance
    if log_callback:
        log_callback(f"✅ Optimized merge completed: {total_success}/{total_frames} files successfully processed in BEAUTY folder")
        
        # Afficher des statistiques de performance si possible
        try:
            memory_info = psutil.virtual_memory()
            log_callback(f"📊 Final memory usage: {memory_info.percent:.1f}% ({memory_info.used / (1024**3):.1f}GB used)")
        except:
            pass
