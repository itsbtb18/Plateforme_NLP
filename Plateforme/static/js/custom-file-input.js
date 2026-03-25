/**
 * Personnalisation des boutons de fichier pour supporter les traductions
 */
document.addEventListener('DOMContentLoaded', function() {
    // Obtenir la langue actuelle
    const currentLang = document.documentElement.lang;
    
    // Traductions
    const translations = {
        'ar': {
            chooseFile: 'اختر ملف',
            noFileChosen: 'لم يتم اختيار ملف',
            chooseImage: 'اختر صورة',
            noImageChosen: 'لم يتم اختيار صورة',
            image: 'صورة',
            file: 'ملف'
        },
        'en': {
            chooseImage: 'Choose image',
            noImageChosen: 'No image chosen',
            image: 'Image',
            file: 'File'
        },
        'fr': {
            chooseFile: 'Choisir un fichier',
            noFileChosen: 'Aucun fichier sélectionné',
            chooseImage: 'Choisir une image',
            noImageChosen: 'Aucune image sélectionnée',
            image: 'Image',
            file: 'Fichier'
        }
    };
    
    const t = translations[currentLang] || translations['en'];
    
    // Personnaliser tous les inputs de type file
    const fileInputs = document.querySelectorAll('input[type="file"]');
    
    fileInputs.forEach(function(input) {
        // Skip inputs that are intentionally hidden (e.g. avatar input on profile page)
        // Also skip the attachment input in events form (uses ef-file-zone instead)
        if (input.style.display === 'none' || input.hidden || input.closest('.custom-file-input-wrapper') || 
            input.id === 'attachmentInput' || input.closest('.ef-file-zone')) {
            return;
        }

        // Créer un wrapper personnalisé
        const wrapper = document.createElement('div');
        wrapper.className = 'custom-file-input-wrapper';
        
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'custom-file-button btn btn-outline-secondary';
        
        // Déterminer si c'est une image ou un fichier général
        const isImage = input.accept && input.accept.includes('image');
        button.textContent = isImage ? t.chooseImage : t.chooseFile;
        
        const fileName = document.createElement('span');
        fileName.className = 'custom-file-name';
        fileName.textContent = isImage ? t.noImageChosen : t.noFileChosen;
        
        // Cacher l'input original
        input.style.display = 'none';
        
        // Insérer les éléments personnalisés
        input.parentNode.insertBefore(wrapper, input);
        wrapper.appendChild(button);
        wrapper.appendChild(fileName);
        wrapper.appendChild(input);
        
        // Gérer le clic sur le bouton
        button.addEventListener('click', function() {
            input.click();
        });
        
        // Afficher le nom du fichier sélectionné
        input.addEventListener('change', function() {
            if (input.files.length > 0) {
                fileName.textContent = input.files[0].name;
            } else {
                fileName.textContent = isImage ? t.noImageChosen : t.noFileChosen;
            }
        });
    });
});
