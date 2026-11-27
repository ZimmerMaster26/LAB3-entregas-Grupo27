### LISTA DE TODO (DE ULTRA BAJA PRIORIDAD -hacer solo si sobra tiempo y tokens-)

- [ ] Rehacer el sistema operativo, pero en vez de tener dos instrucciones especializadas del propio simulador, implementar interrupciones, tabla de interrupciones, controladores de interrupciones, memoria mapeada de dispositivos (KBSR, KBDR, DSR, DDR) (MCR tendrá de bit 15 al *clock enable*, que se pone en 0 al llamar a HALT, y de bit 14 tendrá a *wait for interrupt*, que detendrá el reloj hasta que ocurra una interrupción como cuando se pulsa una tecla, de esta forma GETC no necesitara hacer *bussy waiting*, sino que simplemente esperara la interrupción)

- [ ] Implementar un modulo aparte que se pueda aprovechar usando *Ducktyping* que sea *debugger*, que se pueda utilizar desde dentro del simulador para ir paso a paso, inspeccionar un rango de instrucciones, inspeccionar registros, inspeccionar memoria, inspeccionar *breakpoints*, cambiar valores durante la ejecución, pausar, continuar, paso siguiente, paso ingresante, etc.

- [ ] Aplicación con GUI para trabajar con una interfaz y no desde la consola.

