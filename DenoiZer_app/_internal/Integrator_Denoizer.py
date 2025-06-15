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

# Redéfinir la logique de compression avec OpenImageIO et optimisations
def get_compression(compression_mode, compression_level=None):
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

def process_integrator_frame(frame, input_folder, integrator_dir, selected_integrators, compression_mode, compression_level=None, log_callback=None):
    """Traitement optimisé d'une seule frame pour l'extraction d'intégrateurs"""
    messages = []
    result = False
    start_time = time.time()
    
    def local_log(msg):
        if log_callback:
            log_callback(msg)
        messages.append(msg)
    
    try:
        input_exr = os.path.join(input_folder, frame)
        
        # Utiliser ImageBuf pour lire le fichier complet avec optimisations
        buf = oiio.ImageBuf(input_exr)
        if buf.has_error:
            local_log(f"❌ Impossible d'ouvrir {input_exr}: {buf.geterror()}")
            return result, messages
            
        # Obtenir les informations de l'image
        spec = buf.spec()
        width, height = spec.width, spec.height
        size = (width, height)
        all_channels = spec.channelnames
        
        # Initialiser le dictionnaire pour les canaux à extraire
        output_channels = {}
        import numpy as np

        # Ajouter automatiquement le canal alpha s'il existe (A ou a)
        if 'A' in all_channels:
            try:
                alpha_idx = all_channels.index('A')
                # Extraire le canal alpha avec optimisations
                alpha_buf = oiio.ImageBufAlgo.channels(buf, (alpha_idx,))
                if alpha_buf and not alpha_buf.has_error:
                    pixels = alpha_buf.get_pixels(oiio.FLOAT)
                    if pixels is not None:
                        # S'assurer que les données sont contiguës pour de meilleures performances
                        if isinstance(pixels, np.ndarray) and not pixels.flags['C_CONTIGUOUS']:
                            pixels = np.ascontiguousarray(pixels)
                        output_channels['A'] = pixels
                        local_log(f"✅ Ajouté le canal Alpha (A) depuis l'input pour {frame}")
                    else:
                        local_log(f"⚠️ Could not read Alpha channel (A) data")
                else:
                    local_log(f"⚠️ Error creating Alpha channel buffer")
            except Exception as e:
                local_log(f"⚠️ Error extracting Alpha channel (A): {e}")
        
        # Chercher également le canal 'a' qui est souvent utilisé comme alpha
        if 'a' in all_channels:
            try:
                alpha_idx = all_channels.index('a')
                # Extraire le canal alpha avec optimisations
                alpha_buf = oiio.ImageBufAlgo.channels(buf, (alpha_idx,))
                if alpha_buf and not alpha_buf.has_error:
                    pixels = alpha_buf.get_pixels(oiio.FLOAT)
                    if pixels is not None:
                        # S'assurer que les données sont contiguës pour de meilleures performances
                        if isinstance(pixels, np.ndarray) and not pixels.flags['C_CONTIGUOUS']:
                            pixels = np.ascontiguousarray(pixels)
                        output_channels['a'] = pixels
                        local_log(f"✅ Ajouté le canal alpha (a) depuis l'input pour {frame}")
                    else:
                        local_log(f"⚠️ Could not read alpha channel (a) data")
                else:
                    local_log(f"⚠️ Error creating alpha channel buffer")
            except Exception as e:
                local_log(f"⚠️ Error extracting alpha channel (a): {e}")

        for selected_aov in selected_integrators:
            # Ne pas traiter 'a' comme un intégrateur s'il a déjà été extrait comme alpha
            if selected_aov == 'a' and 'a' in output_channels:
                continue
                
            found_channels = []
            for ch_idx, ch in enumerate(all_channels):
                if ch == selected_aov or ch.startswith(selected_aov + '.'):
                    try:
                        # Extraire le canal avec optimisations
                        channel_buf = oiio.ImageBufAlgo.channels(buf, (ch_idx,))
                        if channel_buf and not channel_buf.has_error:
                            pixels = channel_buf.get_pixels(oiio.FLOAT)
                            if pixels is not None:
                                # S'assurer que les données sont contiguës pour de meilleures performances
                                if isinstance(pixels, np.ndarray) and not pixels.flags['C_CONTIGUOUS']:
                                    pixels = np.ascontiguousarray(pixels)
                                output_channels[ch] = pixels
                                found_channels.append(ch)
                                local_log(f"✅ Trouvé {ch} pour {selected_aov} dans {frame}")
                            else:
                                local_log(f"⚠️ Could not read data for channel {ch}")
                        else:
                            local_log(f"⚠️ Error creating buffer for channel {ch}")
                    except Exception as e:
                        local_log(f"⚠️ Error extracting channel {ch}: {e}")
                        continue

            if not found_channels:
                local_log(f"⚠️ AOV '{selected_aov}' manquant dans {frame}")

        if not output_channels:
            local_log(f"⚠️ Aucun canal valide trouvé pour {frame}")
            return result, messages

        # Créer une nouvelle spécification d'image optimisée pour la sortie
        out_spec = oiio.ImageSpec(width, height, len(output_channels), oiio.FLOAT)
        out_spec.channelnames = list(output_channels.keys())
        
        # Configurer la compression optimisée
        compression, level = get_compression(compression_mode, compression_level)
        out_spec.attribute("compression", compression)
        if level is not None and compression in ["dwaa", "dwab"]:
            out_spec.attribute("compressionlevel", level)
        
        # Optimisations pour les performances d'écriture
        out_spec.tile_width = 64
        out_spec.tile_height = 64
        
        # Attributs supplémentaires pour optimiser les performances
        out_spec.attribute("oiio:ColorSpace", "Linear")
        out_spec.attribute("openexr:lineOrder", "increasingY")
        
        # Optimiser pour les écritures parallèles
        if compression in ["dwaa", "dwab"]:
            out_spec.attribute("openexr:dwaCompressionLevel", level if level else 45)

        filename_no_ext = os.path.splitext(frame)[0]
        if '.' in filename_no_ext:
            base_name, frame_number = filename_no_ext.rsplit('.', 1)
            output_filename = f"{base_name}_INTEGRATOR.{frame_number}.exr"
        else:
            base_name = filename_no_ext
            output_filename = f"{base_name}_INTEGRATOR.exr"

        output_path = os.path.join(integrator_dir, output_filename)

        # Créer un buffer d'image pour la sortie
        out_buf = oiio.ImageBuf(out_spec)
        
        # Organiser les données des pixels dans l'ordre des canaux avec optimisations
        all_pixels = []
        
        for ch in out_spec.channelnames:
            if ch in output_channels:
                pixel_data = output_channels[ch]
                # Vérifier et corriger la forme des données avec optimisations
                if isinstance(pixel_data, np.ndarray):
                    # Si les données ont une dimension supplémentaire, la supprimer
                    if pixel_data.ndim == 4 and pixel_data.shape[2] == 1:
                        pixel_data = pixel_data.squeeze(axis=2)  # Supprimer la dimension de taille 1
                    elif pixel_data.ndim == 3 and pixel_data.shape[2] == 1:
                        pixel_data = pixel_data.squeeze(axis=2)  # Supprimer la dimension de taille 1
                    
                    # S'assurer que les données sont dans le bon format et contiguës
                    if pixel_data.dtype != np.float32:
                        pixel_data = pixel_data.astype(np.float32)
                    if not pixel_data.flags['C_CONTIGUOUS']:
                        pixel_data = np.ascontiguousarray(pixel_data)
                        
                all_pixels.append(pixel_data)
            else:
                # Créer un canal vide si manquant avec le bon type
                empty_channel = np.zeros((height, width), dtype=np.float32)
                all_pixels.append(empty_channel)
        
        # Combiner tous les canaux en un seul tableau avec optimisations
        if all_pixels:
            # Empiler les canaux le long de la dimension des canaux
            combined_pixels = np.stack(all_pixels, axis=-1)
            
            # S'assurer que le tableau final est contiguë pour de meilleures performances d'écriture
            if not combined_pixels.flags['C_CONTIGUOUS']:
                combined_pixels = np.ascontiguousarray(combined_pixels)
                
            out_buf.set_pixels(oiio.ROI(), combined_pixels)

        # Écrire le fichier de sortie avec optimisations
        success = out_buf.write(output_path)
        if not success:
            local_log(f"❌ Erreur lors de l'écriture: {output_path}")
            return result, messages

        # Calculer et afficher les statistiques de performance
        elapsed_time = time.time() - start_time
        try:
            file_size = os.path.getsize(output_path) / (1024 * 1024)  # Taille en MB
            local_log(f"✅ Integrator généré : {output_path} ({file_size:.1f}MB en {elapsed_time:.2f}s)")
        except:
            local_log(f"✅ Integrator généré : {output_path} en {elapsed_time:.2f}s")
        
        result = True

    except Exception as e:
        local_log(f"❌ Error generating Integrator for {frame} : {e}")
    
    return result, messages

def run_integrator_generate(input_folder, output_folder, selected_integrators, compression_mode="DWAB", compression_level=None, log_callback=None, progress_callback=None, stop_check=None, use_gpu=False):
    """Extract selected integrators from EXR files with optimized performance"""
    
    # Tenter de définir une priorité élevée pour ce processus
    priority_set = set_high_priority()
    
    # Optimiser l'utilisation de la mémoire
    memory_optimized = optimize_memory_usage()
    
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
        log_callback("🔄 Starting optimized integrator generation...")
        if priority_set:
            log_callback("⚡ High priority mode enabled for faster processing")
        if memory_optimized:
            log_callback("🧠 Memory usage optimized for better performance")
        if gpu_acceleration:
            log_callback("🎮 Using GPU acceleration for faster image operations")
        if compression_mode in ["DWAA", "DWAB"] and compression_level is not None:
            log_callback(f"📊 Using compression level: {compression_level} for {compression_mode} compression")

    # Créer le répertoire de sortie s'il n'existe pas
    os.makedirs(output_folder, exist_ok=True)

    # Obtenir la liste des fichiers EXR dans le dossier d'entrée
    exr_files = [f for f in os.listdir(input_folder) if f.lower().endswith('.exr')]
    if not exr_files:
        if log_callback:
            log_callback("❌ No EXR files found in input folder")
        return False

    # Déterminer le nombre optimal de workers avec optimisations
    optimal_workers = get_optimal_thread_count()
    # Ajuster selon le nombre de fichiers disponibles
    optimal_workers = min(optimal_workers, len(exr_files))
    
    if log_callback:
        log_callback(f"📊 Using {optimal_workers} optimized parallel workers for processing")
        
        # Afficher des informations sur les ressources système
        try:
            memory_gb = psutil.virtual_memory().available / (1024**3)
            cpu_count = multiprocessing.cpu_count()
            log_callback(f"💻 System resources: {cpu_count} CPU cores, {memory_gb:.1f}GB available memory")
        except:
            pass

    # Traiter les fichiers en parallèle avec optimisations
    total_success = 0
    total_files = len(exr_files)
    files_processed = 0
    start_time = time.time()
    
    # Diviser les fichiers en batches pour optimiser la mémoire
    batch_size = max(1, min(optimal_workers * 2, 10))  # Traiter par petits batches
    batches = [exr_files[i:i + batch_size] for i in range(0, len(exr_files), batch_size)]
    
    if log_callback:
        log_callback(f"📦 Processing {total_files} files in {len(batches)} batches of {batch_size} files each")

    for batch_index, batch in enumerate(batches):
        if log_callback:
            log_callback(f"🔄 Processing batch {batch_index + 1}/{len(batches)} ({len(batch)} files)")
        
        batch_start_time = time.time()
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=optimal_workers) as executor:
            futures = []
            for frame in batch:
                future = executor.submit(
                    process_integrator_frame,
                    frame,
                    input_folder,
                    output_folder,
                    selected_integrators,
                    compression_mode,
                    compression_level,
                    None  # On gère les logs nous-mêmes pour éviter les concurrences
                )
                futures.append((frame, future))

            # Surveiller la progression du batch
            for frame, future in futures:
                # Check for stop request
                if stop_check and stop_check():
                    if log_callback:
                        log_callback(f"🛑 Process stopped by user (at file {files_processed+1}/{total_files})")
                    # Cancel all pending futures
                    for _, f in futures:
                        f.cancel()
                    return False

                try:
                    result, messages = future.result()
                    if result:
                        total_success += 1
                    
                    # Logs par frame
                    if log_callback and messages:
                        log_callback(f"⏳ Processing file: {frame}")
                        for msg in messages:
                            log_callback(f"  {msg}")
                except Exception as e:
                    if log_callback:
                        log_callback(f"❌ Error processing file {frame}: {str(e)}")

                # Mettre à jour la progression
                files_processed += 1
                progress_percent = files_processed / total_files * 100
                
                if log_callback and files_processed % max(1, total_files//10) == 0:  # Limiter les logs de progression
                    log_callback(f"⏳ Progress: {files_processed}/{total_files} files processed")
                
                if progress_callback:
                    should_stop = progress_callback(progress_percent)
                    if should_stop:
                        if log_callback:
                            log_callback(f"🛑 Process stopped by progress callback")
                        # Cancel all pending futures
                        for _, f in futures:
                            f.cancel()
                        return False
        
        # Statistiques par batch et optimisation mémoire
        batch_time = time.time() - batch_start_time
        if log_callback and len(batches) > 1:
            log_callback(f"✅ Batch {batch_index+1}/{len(batches)} completed in {batch_time:.2f}s ({len(batch)/batch_time:.2f} frames/s)")
        
        # Optimiser la mémoire entre les batches
        if batch_index < len(batches) - 1:  # Pas le dernier batch
            try:
                import gc
                gc.collect()
                optimize_memory_usage()
            except:
                pass

    # Statistiques finales avec informations de performance
    total_time = time.time() - start_time
    
    if log_callback:
        # Calculer les statistiques de performance
        if total_time > 0:
            files_per_second = total_files / total_time
            avg_time_per_file = total_time / total_files if total_files > 0 else 0
            
            # Formater le temps total
            if total_time < 60:
                time_str = f"{total_time:.1f}s"
            elif total_time < 3600:
                time_str = f"{int(total_time//60)}m {int(total_time%60)}s"
            else:
                time_str = f"{int(total_time//3600)}h {int((total_time%3600)//60)}m"
            
            log_callback(f"✅ Integrator generation completed: {total_success}/{total_files} files successfully processed")
            log_callback(f"📊 Performance: {files_per_second:.2f} files/s, {avg_time_per_file:.2f}s per file, total time: {time_str}")
            
            # Afficher des informations sur l'efficacité
            if total_success == total_files:
                log_callback(f"🎯 Perfect success rate: 100% of files processed successfully")
            elif total_success > 0:
                success_rate = (total_success / total_files) * 100
                log_callback(f"⚠️ Partial success: {success_rate:.1f}% of files processed successfully")
            else:
                log_callback(f"❌ No files were processed successfully")
        else:
            log_callback(f"✅ Integrator generation completed: {total_success}/{total_files} files successfully processed")
    
    return total_success > 0
