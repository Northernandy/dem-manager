/*
 * Leaflet.ImageTransform
 * A plugin for Leaflet that enables image overlays with arbitrary corners
 * https://github.com/ScanEx/Leaflet.imageTransform
 */

L.ImageTransform = L.ImageOverlay.extend({
    initialize: function (url, anchors, options) {
        L.ImageOverlay.prototype.initialize.call(this, url, anchors, options);
        this.setAnchors(anchors);
    },

    setAnchors: function (anchors) {
        this._anchors = anchors;
        this._bounds = L.latLngBounds(anchors);
    },

    _initImage: function () {
        L.ImageOverlay.prototype._initImage.call(this);
        L.DomUtil.addClass(this._image, 'leaflet-image-transform');
    },

    _reset: function () {
        var image = this._image,
            bounds = new L.Bounds(
                this._map.latLngToLayerPoint(this._bounds.getNorthWest()),
                this._map.latLngToLayerPoint(this._bounds.getSouthEast())),
            size = bounds.getSize();

        L.DomUtil.setPosition(image, bounds.min);

        image.style.width = size.x + 'px';
        image.style.height = size.y + 'px';

        this._updateCorners();
    },

    _updateCorners: function () {
        if (!this._map) { return; }

        var corners = {},
            anchors = this._anchors;

        for (var i = 0, len = anchors.length; i < len; i++) {
            corners[i] = this._map.latLngToLayerPoint(anchors[i]);
        }

        this._transformImage(corners);
    },

    _transformImage: function (corners) {
        var matrix3d = '',
            image = this._image,
            cornerTR = corners[1],
            cornerBR = corners[2],
            cornerBL = corners[3],
            cornerTL = corners[0];

        // Ensure the image covers the whole area
        var topRight = new L.Point(cornerTR.x - cornerTL.x, cornerTR.y - cornerTL.y),
            bottomRight = new L.Point(cornerBR.x - cornerTL.x, cornerBR.y - cornerTL.y),
            bottomLeft = new L.Point(cornerBL.x - cornerTL.x, cornerBL.y - cornerTL.y);

        // Calculate the transformation matrix
        var matrix = this._general2DProjection(
            0, 0, topRight.x, topRight.y,
            bottomLeft.x, bottomLeft.y, bottomRight.x, bottomRight.y,
            0, 0, image.width, 0,
            0, image.height, image.width, image.height
        );

        // Apply the transformation
        if (L.Browser.gecko) {
            matrix3d = 'matrix3d(' +
                matrix[0].toFixed(10) + ',' + matrix[3].toFixed(10) + ',0,0,' +
                matrix[1].toFixed(10) + ',' + matrix[4].toFixed(10) + ',0,0,' +
                '0,0,1,0,' +
                matrix[2].toFixed(10) + ',' + matrix[5].toFixed(10) + ',0,1)';
        } else {
            matrix3d = 'matrix3d(' +
                matrix[0].toFixed(6) + ',' + matrix[3].toFixed(6) + ',0,0,' +
                matrix[1].toFixed(6) + ',' + matrix[4].toFixed(6) + ',0,0,' +
                '0,0,1,0,' +
                matrix[2].toFixed(6) + ',' + matrix[5].toFixed(6) + ',0,1)';
        }

        image.style[L.DomUtil.TRANSFORM] = matrix3d;
    },

    _general2DProjection: function (
        x1s, y1s, x2s, y2s, x3s, y3s, x4s, y4s,
        x1d, y1d, x2d, y2d, x3d, y3d, x4d, y4d
    ) {
        var s = this._computeProjectiveTransform(
            x1s, y1s, x2s, y2s, x3s, y3s, x4s, y4s,
            x1d, y1d, x2d, y2d, x3d, y3d, x4d, y4d
        );

        return [
            s[0], s[3], s[6],
            s[1], s[4], s[7],
            s[2], s[5], s[8]
        ];
    },

    _computeProjectiveTransform: function (
        x1s, y1s, x2s, y2s, x3s, y3s, x4s, y4s,
        x1d, y1d, x2d, y2d, x3d, y3d, x4d, y4d
    ) {
        var r1 = [x1s, y1s, 1, 0, 0, 0, -x1d * x1s, -x1d * y1s],
            r2 = [0, 0, 0, x1s, y1s, 1, -y1d * x1s, -y1d * y1s],
            r3 = [x2s, y2s, 1, 0, 0, 0, -x2d * x2s, -x2d * y2s],
            r4 = [0, 0, 0, x2s, y2s, 1, -y2d * x2s, -y2d * y2s],
            r5 = [x3s, y3s, 1, 0, 0, 0, -x3d * x3s, -x3d * y3s],
            r6 = [0, 0, 0, x3s, y3s, 1, -y3d * x3s, -y3d * y3s],
            r7 = [x4s, y4s, 1, 0, 0, 0, -x4d * x4s, -x4d * y4s],
            r8 = [0, 0, 0, x4s, y4s, 1, -y4d * x4s, -y4d * y4s];

        var matA = [r1, r2, r3, r4, r5, r6, r7, r8],
            matB = [x1d, y1d, x2d, y2d, x3d, y3d, x4d, y4d],
            matC;

        try {
            matC = this._gaussJordan(matA, matB);
        } catch (e) {
            console.error('Error computing transform: ' + e.message);
            return [1, 0, 0, 0, 1, 0, 0, 0, 1]; // Identity transform as fallback
        }

        matC.push(1);
        return matC;
    },

    _gaussJordan: function (a, b) {
        var n = a.length,
            m = a[0].length,
            i, j, k, l, h, temp;

        // Perform Gaussian elimination
        for (i = 0; i < n; i++) {
            // Find pivot
            h = i;
            for (j = i + 1; j < n; j++) {
                if (Math.abs(a[j][i]) > Math.abs(a[h][i])) {
                    h = j;
                }
            }

            // Swap rows
            temp = a[h];
            a[h] = a[i];
            a[i] = temp;

            temp = b[h];
            b[h] = b[i];
            b[i] = temp;

            // Singular matrix check
            if (Math.abs(a[i][i]) < 1e-10) {
                throw new Error('Matrix is singular or nearly singular');
            }

            // Scale row
            var pivot = a[i][i];
            for (j = i; j < m; j++) {
                a[i][j] /= pivot;
            }
            b[i] /= pivot;

            // Eliminate other rows
            for (j = 0; j < n; j++) {
                if (j !== i) {
                    var factor = a[j][i];
                    for (k = i; k < m; k++) {
                        a[j][k] -= factor * a[i][k];
                    }
                    b[j] -= factor * b[i];
                }
            }
        }

        return b;
    }
});

L.imageTransform = function (url, bounds, options) {
    return new L.ImageTransform(url, bounds, options);
};
