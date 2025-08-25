/**
 * Clase para manejar el recorte de imágenes usando Cropper.js
 */
class ImageCropper {
    constructor() {
        this.cropper = null;
        this.modal = null;
        this.callback = null;
        // No crear el modal inmediatamente
    }

    /**
     * Crea el modal de recorte (solo cuando sea necesario)
     */
    createModal() {
        if (this.modal) return; // Ya existe
        
        this.modal = document.createElement('div');
        this.modal.className = 'crop-modal';
        this.modal.innerHTML = `
            <div class="crop-modal-content">
                <h3 style="color: #ffffff; margin-bottom: 20px; text-align: center;">Recortar Imagen</h3>
                <div class="crop-container">
                    <img id="crop-image" style="max-width: 100%; height: auto;">
                </div>
                <div class="crop-controls">
                    <button class="crop-btn cancel" id="crop-cancel">Cancelar</button>
                    <button class="crop-btn" id="crop-confirm">Confirmar</button>
                </div>
            </div>
        `;
        document.body.appendChild(this.modal);

        // Event listeners
        this.modal.querySelector('#crop-cancel').addEventListener('click', () => this.close());
        this.modal.querySelector('#crop-confirm').addEventListener('click', () => this.confirm());
        
        // Cerrar con ESC
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.modal && this.modal.style.display === 'flex') {
                this.close();
            }
        });
    }

    /**
     * Abre el modal de recorte con una imagen
     * @param {File} file - Archivo de imagen
     * @param {Function} callback - Función a ejecutar con la imagen recortada
     * @param {Object} options - Opciones de recorte
     */
    async open(file, callback, options = {}) {
        if (!file || !file.type.startsWith('image/')) {
            Swal.fire('Error', 'Por favor selecciona un archivo de imagen válido.', 'error');
            return;
        }

        // Crear el modal solo cuando sea necesario
        this.createModal();
        
        // Asegurar que Cropper.js esté cargado
        await loadCropperJS();

        this.callback = callback;
        const reader = new FileReader();
        
        reader.onload = (e) => {
            const image = this.modal.querySelector('#crop-image');
            image.src = e.target.result;
            
            // Configuración por defecto del cropper
            const defaultOptions = {
                aspectRatio: options.aspectRatio || 1, // Cuadrado por defecto
                viewMode: 1,
                dragMode: 'move',
                autoCropArea: 0.8,
                restore: false,
                guides: true,
                center: true,
                highlight: false,
                cropBoxMovable: true,
                cropBoxResizable: true,
                toggleDragModeOnDblclick: false,
                background: false,
                responsive: true,
                checkOrientation: false,
                modal: true,
                ...options
            };

            // Destruir cropper anterior si existe
            if (this.cropper) {
                this.cropper.destroy();
            }

            // Inicializar cropper cuando la imagen se cargue
            image.addEventListener('load', () => {
                if (window.Cropper) {
                    this.cropper = new Cropper(image, defaultOptions);
                } else {
                    console.error('Cropper.js no está disponible');
                    Swal.fire('Error', 'Error al cargar el recortador de imágenes', 'error');
                }
            }, { once: true });

            this.modal.style.display = 'flex';
        };

        reader.readAsDataURL(file);
    }

    /**
     * Confirma el recorte y ejecuta el callback
     */
    confirm() {
        if (!this.cropper || !this.callback) return;

        // Obtener canvas con la imagen recortada
        const canvas = this.cropper.getCroppedCanvas({
            width: 500,
            height: 500,
            imageSmoothingEnabled: true,
            imageSmoothingQuality: 'high',
        });

        // Convertir a blob
        canvas.toBlob((blob) => {
            const file = new File([blob], 'cropped-image.jpg', {
                type: 'image/jpeg',
                lastModified: Date.now()
            });

            this.callback(file, canvas.toDataURL('image/jpeg', 0.9));
            this.close();
        }, 'image/jpeg', 0.9);
    }

    /**
     * Cierra el modal
     */
    close() {
        if (this.cropper) {
            this.cropper.destroy();
            this.cropper = null;
        }
        if (this.modal) {
            this.modal.style.display = 'none';
        }
        this.callback = null;
    }
}

// Crear instancia global solo cuando sea necesaria
let imageCropper = null;

// Función para obtener la instancia del cropper (lazy loading)
function getImageCropper() {
    if (!imageCropper) {
        imageCropper = new ImageCropper();
    }
    return imageCropper;
}

// Exponer globalmente ambas formas para compatibilidad
window.getImageCropper = getImageCropper;
window.imageCropper = getImageCropper(); // Para retrocompatibilidad

/**
 * Función helper para cargar Cropper.js
 */
async function loadCropperJS() {
    if (window.Cropper) return; // Ya está cargado

    // Cargar CSS
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = 'https://cdnjs.cloudflare.com/ajax/libs/cropperjs/1.5.13/cropper.min.css';
    document.head.appendChild(link);

    // Cargar JS
    const script = document.createElement('script');
    script.src = 'https://cdnjs.cloudflare.com/ajax/libs/cropperjs/1.5.13/cropper.min.js';
    
    return new Promise((resolve, reject) => {
        script.onload = resolve;
        script.onerror = reject;
        document.head.appendChild(script);
    });
}

// Cargar Cropper.js cuando sea necesario (no automáticamente)
// document.addEventListener('DOMContentLoaded', () => {
//     loadCropperJS().catch(console.error);
// });