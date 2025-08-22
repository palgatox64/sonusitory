import subprocess
import threading
import signal
import sys
import os
from django.core.management.base import BaseCommand
from django.core.management import execute_from_command_line


class Command(BaseCommand):
    help = 'Ejecuta el servidor de desarrollo y el worker de Celery simultáneamente'

    def add_arguments(self, parser):
        parser.add_argument(
            '--port',
            type=str,
            default='8000',
            help='Puerto para el servidor Django (default: 8000)'
        )

    def handle(self, *args, **options):
        port = options['port']
        
        # Variables para controlar los procesos
        self.django_process = None
        self.celery_process = None
        
        # Función para ejecutar el servidor Django
        def run_django():
            self.stdout.write(self.style.SUCCESS('🚀 Iniciando servidor Django...'))
            try:
                # Ejecutar runserver en un subproceso
                self.django_process = subprocess.Popen([
                    sys.executable, 'manage.py', 'runserver', f'127.0.0.1:{port}'
                ])
                self.django_process.wait()
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error al iniciar Django: {e}'))
        
        # Función para ejecutar Celery worker
        def run_celery():
            self.stdout.write(self.style.SUCCESS('🔄 Iniciando Celery worker...'))
            try:
                self.celery_process = subprocess.Popen([
                    sys.executable, '-m', 'celery', 
                    '-A', 'core', 'worker', 
                    '-l', 'info', '-P', 'solo'
                ])
                self.celery_process.wait()
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error al iniciar Celery: {e}'))
        
        # Función para manejar la señal de interrupción
        def signal_handler(sig, frame):
            self.stdout.write(self.style.WARNING('\n⚠️  Deteniendo servicios...'))
            
            # Terminar procesos si están ejecutándose
            if self.django_process:
                self.django_process.terminate()
            if self.celery_process:
                self.celery_process.terminate()
            
            sys.exit(0)
        
        # Configurar el manejador de señales
        signal.signal(signal.SIGINT, signal_handler)
        
        # Crear threads para ambos procesos
        django_thread = threading.Thread(target=run_django, daemon=True)
        celery_thread = threading.Thread(target=run_celery, daemon=True)
        
        try:
            # Iniciar ambos threads
            django_thread.start()
            celery_thread.start()
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'✅ Servicios iniciados:\n'
                    f'   - Django: http://127.0.0.1:{port}\n'
                    f'   - Celery worker ejecutándose\n'
                    f'   Presiona Ctrl+C para detener ambos servicios\n'
                )
            )
            
            # Mantener el proceso principal vivo
            while django_thread.is_alive() or celery_thread.is_alive():
                django_thread.join(timeout=1)
                celery_thread.join(timeout=1)
            
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING('⚠️  Servicios detenidos'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error inesperado: {e}'))
        finally:
            # Asegurar que los procesos se terminen
            if self.django_process:
                self.django_process.terminate()
            if self.celery_process:
                self.celery_process.terminate()
