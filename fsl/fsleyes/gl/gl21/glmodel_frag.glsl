/*
 * Fragment shader used for drawing GLModel instances.
 *
 * Author: Paul McCarthy <pauldmccarthy@gmail.com> 
 */
#version 120

#pragma include edge.glsl

uniform sampler2D tex;
uniform vec2      offsets;
varying vec2      texCoord;

void main(void) {
  
  vec4 colour = texture2D(tex, texCoord);
  vec4 tol    = 1.0 / vec4(255, 255, 255, 255);

  /*
   * If the fragment lies on an edge
   * colour it, otherwise clear it.
   */
  if (edge2D(tex, texCoord, colour, tol, offsets)) gl_FragColor   = colour;
  else                                             gl_FragColor.a = 0.0;
}
