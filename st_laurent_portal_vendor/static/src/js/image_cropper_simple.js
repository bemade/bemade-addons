/* Cropper.js integration for vendor product images */
$(document).ready(function() {
    var $image = $('#image-preview');
    var $inputFile = $('#product_image');
    var $cropButton = $('#crop-button');
    var $cropperContainer = $('#cropper-container');
    var $imageContainer = $('#image-container');
    var $croppedImageInput = $('#cropped_image');
    var $cropperControls = $('.cropper-controls');
    var $aspectRatioButtons = $('.aspect-ratio-button');
    var $zoomInButton = $('#zoom-in');
    var $zoomOutButton = $('#zoom-out');
    var $rotateLeftButton = $('#rotate-left');
    var $rotateRightButton = $('#rotate-right');
    var $resetButton = $('#reset-cropper');
    var cropper;

    // Fonction pour initialiser le cropper
    function initCropper() {
        if (cropper) {
            cropper.destroy();
        }

        // Initialiser le cropper avec les options par défaut
        cropper = new Cropper($image[0], {
            aspectRatio: NaN, // Aspect ratio libre par défaut
            viewMode: 1, // Restreint la zone de recadrage à l'image
            autoCropArea: 0.8, // 80% de la zone de l'image
            responsive: true,
            restore: false,
            guides: true,
            center: true,
            highlight: true,
            cropBoxMovable: true,
            cropBoxResizable: true,
            toggleDragModeOnDblclick: true,
            ready: function() {
                $cropperControls.removeClass('d-none');
            }
        });
    }

    // Gestion de l'upload d'image
    $inputFile.on('change', function (e) {
        var files = e.target.files;
        var done = function (url) {
            $inputFile.val('');
            $image.attr('src', url);
            $cropperContainer.removeClass('d-none');
            $imageContainer.addClass('d-none');
            $cropButton.removeClass('d-none');
            initCropper();
        };

        if (files && files.length > 0) {
            var file = files[0];
            
            // Vérifier le type de fichier
            if (!/^image\/(jpeg|png|gif)$/.test(file.type)) {
                alert('Veuillez sélectionner une image valide (JPG, PNG ou GIF).');
                return;
            }
            
            // Vérifier la taille du fichier (max 5 Mo)
            if (file.size > 5 * 1024 * 1024) {
                alert("L'image est trop volumineuse. La taille maximale est de 5 Mo.");
                return;
            }

            var reader = new FileReader();
            reader.onload = function (e) {
                done(reader.result);
            };
            reader.readAsDataURL(file);
        }
    });

    // Gestion du recadrage
    $cropButton.on('click', function () {
        if (!cropper) {
            return;
        }

        var canvas = cropper.getCroppedCanvas({
            width: 1920,
            height: 1920,
            fillColor: '#fff',
            imageSmoothingEnabled: true,
            imageSmoothingQuality: 'high',
        });

        if (canvas) {
            // Convertir le canvas en base64
            var croppedImageData = canvas.toDataURL('image/jpeg', 0.9);
            $croppedImageInput.val(croppedImageData);
            
            // Soumettre le formulaire
            $('#image-upload-form').submit();
        }
    });

    // Gestion des boutons de ratio d'aspect
    $aspectRatioButtons.on('click', function() {
        $aspectRatioButtons.removeClass('active');
        $(this).addClass('active');
        
        var ratio = $(this).data('ratio');
        if (ratio === 'free') {
            cropper.setAspectRatio(NaN);
        } else if (ratio === 'square') {
            cropper.setAspectRatio(1);
        } else if (ratio === '4:3') {
            cropper.setAspectRatio(4/3);
        } else if (ratio === '16:9') {
            cropper.setAspectRatio(16/9);
        }
    });

    // Zoom in
    $zoomInButton.on('click', function() {
        cropper.zoom(0.1);
    });

    // Zoom out
    $zoomOutButton.on('click', function() {
        cropper.zoom(-0.1);
    });

    // Rotation gauche
    $rotateLeftButton.on('click', function() {
        cropper.rotate(-90);
    });

    // Rotation droite
    $rotateRightButton.on('click', function() {
        cropper.rotate(90);
    });

    // Reset
    $resetButton.on('click', function() {
        cropper.reset();
    });
});
