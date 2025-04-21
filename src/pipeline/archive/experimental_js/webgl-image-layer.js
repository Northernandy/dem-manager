/**
 * WebGLImageLayer - A WebGL-based image layer for Leaflet that can handle very large images efficiently.
 * This class uses WebGL to render large images directly on the GPU, avoiding browser memory limitations.
 */

L.WebGLImageLayer = L.Layer.extend({
    options: {
        opacity: 1.0,
        interactive: false,
        crossOrigin: true,
        maxNativeZoom: 18,
        minNativeZoom: 0
    },

    initialize: function(url, bounds, options) {
        this._url = url;
        this._bounds = L.latLngBounds(bounds);
        L.setOptions(this, options);
        
        this._canvas = null;
        this._gl = null;
        this._texture = null;
        this._program = null;
        this._image = null;
        this._isLoaded = false;
        this._isLoading = false;
    },

    onAdd: function(map) {
        this._map = map;
        
        if (!this._canvas) {
            this._initCanvas();
        }

        map.getPanes().overlayPane.appendChild(this._canvas);
        map.on('moveend', this._reset, this);
        
        if (map.options.zoomAnimation && L.Browser.any3d) {
            map.on('zoomanim', this._animateZoom, this);
        }
        
        this._reset();
        this._loadImage();
    },

    onRemove: function(map) {
        map.getPanes().overlayPane.removeChild(this._canvas);
        map.off('moveend', this._reset, this);
        
        if (map.options.zoomAnimation) {
            map.off('zoomanim', this._animateZoom, this);
        }
        
        this._destroyWebGL();
    },

    setOpacity: function(opacity) {
        this.options.opacity = opacity;
        
        if (this._canvas) {
            this._updateOpacity();
        }
        
        return this;
    },

    bringToFront: function() {
        if (this._canvas) {
            this._map.getPanes().overlayPane.appendChild(this._canvas);
        }
        
        return this;
    },

    bringToBack: function() {
        if (this._canvas) {
            const pane = this._map.getPanes().overlayPane;
            pane.insertBefore(this._canvas, pane.firstChild);
        }
        
        return this;
    },

    getAttribution: function() {
        return this.options.attribution;
    },

    _initCanvas: function() {
        this._canvas = L.DomUtil.create('canvas', 'leaflet-webgl-layer');
        
        const size = this._map.getSize();
        this._canvas.width = size.x;
        this._canvas.height = size.y;
        
        L.DomUtil.addClass(this._canvas, 'leaflet-zoom-animated');
        
        // Initialize WebGL context
        this._initWebGL();
    },

    _initWebGL: function() {
        try {
            this._gl = this._canvas.getContext('webgl', { 
                alpha: true, 
                premultipliedAlpha: false,
                antialias: true 
            });
            
            if (!this._gl) {
                console.error('WebGL not supported');
                return;
            }
            
            // Create shader program
            this._program = this._createProgram(
                this._createShader(this._gl.VERTEX_SHADER, this._getVertexShaderSource()),
                this._createShader(this._gl.FRAGMENT_SHADER, this._getFragmentShaderSource())
            );
            
            // Set up buffers
            const vertices = new Float32Array([
                -1.0, -1.0, 0.0, 1.0,
                 1.0, -1.0, 1.0, 1.0,
                -1.0,  1.0, 0.0, 0.0,
                 1.0,  1.0, 1.0, 0.0
            ]);
            
            const vertexBuffer = this._gl.createBuffer();
            this._gl.bindBuffer(this._gl.ARRAY_BUFFER, vertexBuffer);
            this._gl.bufferData(this._gl.ARRAY_BUFFER, vertices, this._gl.STATIC_DRAW);
            
            // Set up attributes
            const positionLocation = this._gl.getAttribLocation(this._program, 'a_position');
            const texCoordLocation = this._gl.getAttribLocation(this._program, 'a_texCoord');
            
            this._gl.vertexAttribPointer(positionLocation, 2, this._gl.FLOAT, false, 16, 0);
            this._gl.vertexAttribPointer(texCoordLocation, 2, this._gl.FLOAT, false, 16, 8);
            
            this._gl.enableVertexAttribArray(positionLocation);
            this._gl.enableVertexAttribArray(texCoordLocation);
            
            // Create texture
            this._texture = this._gl.createTexture();
            this._gl.bindTexture(this._gl.TEXTURE_2D, this._texture);
            
            // Set texture parameters
            this._gl.texParameteri(this._gl.TEXTURE_2D, this._gl.TEXTURE_WRAP_S, this._gl.CLAMP_TO_EDGE);
            this._gl.texParameteri(this._gl.TEXTURE_2D, this._gl.TEXTURE_WRAP_T, this._gl.CLAMP_TO_EDGE);
            this._gl.texParameteri(this._gl.TEXTURE_2D, this._gl.TEXTURE_MIN_FILTER, this._gl.LINEAR);
            this._gl.texParameteri(this._gl.TEXTURE_2D, this._gl.TEXTURE_MAG_FILTER, this._gl.LINEAR);
            
            // Set up uniforms
            this._opacityLocation = this._gl.getUniformLocation(this._program, 'u_opacity');
            this._matrixLocation = this._gl.getUniformLocation(this._program, 'u_matrix');
            
            // Set clear color
            this._gl.clearColor(0.0, 0.0, 0.0, 0.0);
            
        } catch (e) {
            console.error('Error initializing WebGL:', e);
        }
    },

    _createShader: function(type, source) {
        const shader = this._gl.createShader(type);
        this._gl.shaderSource(shader, source);
        this._gl.compileShader(shader);
        
        if (!this._gl.getShaderParameter(shader, this._gl.COMPILE_STATUS)) {
            const info = this._gl.getShaderInfoLog(shader);
            this._gl.deleteShader(shader);
            throw new Error('Could not compile WebGL shader: ' + info);
        }
        
        return shader;
    },

    _createProgram: function(vertexShader, fragmentShader) {
        const program = this._gl.createProgram();
        this._gl.attachShader(program, vertexShader);
        this._gl.attachShader(program, fragmentShader);
        this._gl.linkProgram(program);
        
        if (!this._gl.getProgramParameter(program, this._gl.LINK_STATUS)) {
            const info = this._gl.getProgramInfoLog(program);
            this._gl.deleteProgram(program);
            throw new Error('Could not link WebGL program: ' + info);
        }
        
        return program;
    },

    _getVertexShaderSource: function() {
        return `
            attribute vec2 a_position;
            attribute vec2 a_texCoord;
            
            uniform mat4 u_matrix;
            
            varying vec2 v_texCoord;
            
            void main() {
                gl_Position = u_matrix * vec4(a_position, 0.0, 1.0);
                v_texCoord = a_texCoord;
            }
        `;
    },

    _getFragmentShaderSource: function() {
        return `
            precision mediump float;
            
            uniform sampler2D u_image;
            uniform float u_opacity;
            
            varying vec2 v_texCoord;
            
            void main() {
                vec4 color = texture2D(u_image, v_texCoord);
                gl_FragColor = vec4(color.rgb, color.a * u_opacity);
            }
        `;
    },

    _loadImage: function() {
        if (this._isLoading || this._isLoaded) {
            return;
        }
        
        this._isLoading = true;
        
        const image = new Image();
        
        if (this.options.crossOrigin) {
            image.crossOrigin = 'anonymous';
        }
        
        image.onload = () => {
            this._image = image;
            this._isLoaded = true;
            this._isLoading = false;
            
            if (this._gl) {
                this._updateTexture();
                this._reset();
            }
        };
        
        image.onerror = (e) => {
            this._isLoading = false;
            console.error('Error loading image:', e);
        };
        
        image.src = this._url;
    },

    _updateTexture: function() {
        if (!this._gl || !this._image) {
            return;
        }
        
        this._gl.bindTexture(this._gl.TEXTURE_2D, this._texture);
        this._gl.texImage2D(this._gl.TEXTURE_2D, 0, this._gl.RGBA, this._gl.RGBA, this._gl.UNSIGNED_BYTE, this._image);
    },

    _updateOpacity: function() {
        if (!this._gl) {
            return;
        }
        
        this._gl.useProgram(this._program);
        this._gl.uniform1f(this._opacityLocation, this.options.opacity);
        this._render();
    },

    _reset: function() {
        const topLeft = this._map.containerPointToLayerPoint([0, 0]);
        L.DomUtil.setPosition(this._canvas, topLeft);
        
        const size = this._map.getSize();
        
        if (this._canvas.width !== size.x || this._canvas.height !== size.y) {
            this._canvas.width = size.x;
            this._canvas.height = size.y;
        }
        
        this._render();
    },

    _render: function() {
        if (!this._gl || !this._isLoaded) {
            return;
        }
        
        const bounds = this._bounds;
        const mapSize = this._map.getSize();
        const nw = this._map.latLngToContainerPoint(bounds.getNorthWest());
        const se = this._map.latLngToContainerPoint(bounds.getSouthEast());
        
        // Calculate transformation matrix
        const width = se.x - nw.x;
        const height = se.y - nw.y;
        
        // Skip rendering if image is outside the viewport
        if (width <= 0 || height <= 0 || 
            nw.x > mapSize.x || nw.y > mapSize.y || 
            se.x < 0 || se.y < 0) {
            return;
        }
        
        // Set viewport
        this._gl.viewport(0, 0, this._canvas.width, this._canvas.height);
        
        // Clear canvas
        this._gl.clear(this._gl.COLOR_BUFFER_BIT);
        
        // Use shader program
        this._gl.useProgram(this._program);
        
        // Calculate transformation matrix
        const scaleX = width / this._canvas.width;
        const scaleY = height / this._canvas.height;
        const translateX = (2 * nw.x / this._canvas.width) - 1;
        const translateY = 1 - (2 * nw.y / this._canvas.height);
        
        const matrix = [
            scaleX, 0, 0, 0,
            0, scaleY, 0, 0,
            0, 0, 1, 0,
            translateX, translateY, 0, 1
        ];
        
        // Set uniforms
        this._gl.uniformMatrix4fv(this._matrixLocation, false, matrix);
        this._gl.uniform1f(this._opacityLocation, this.options.opacity);
        
        // Bind texture
        this._gl.activeTexture(this._gl.TEXTURE0);
        this._gl.bindTexture(this._gl.TEXTURE_2D, this._texture);
        
        // Draw
        this._gl.drawArrays(this._gl.TRIANGLE_STRIP, 0, 4);
    },

    _animateZoom: function(e) {
        const scale = this._map.getZoomScale(e.zoom);
        const offset = this._map._getCenterOffset(e.center)._multiplyBy(-scale).subtract(this._map._getMapPanePos());
        
        if (L.Browser.any3d) {
            L.DomUtil.setTransform(this._canvas, offset, scale);
        } else {
            L.DomUtil.setPosition(this._canvas, offset);
        }
    },

    _destroyWebGL: function() {
        if (!this._gl) {
            return;
        }
        
        // Delete WebGL resources
        this._gl.deleteTexture(this._texture);
        this._gl.deleteProgram(this._program);
        
        this._gl = null;
        this._program = null;
        this._texture = null;
    }
});

L.webGLImageLayer = function(url, bounds, options) {
    return new L.WebGLImageLayer(url, bounds, options);
};
