# Maintainer: Jason McGillivray <`echo 2f27c627c3b3f7cb676944bbc9cb792ff991dd6a== | base64 -d`>


pkgname=amdfan
pkgdesc="Python daemon for controlling the fans on amdgpu cards"
pkgver=0.1.6
pkgrel=1
arch=('any')
license=('GPL2')
depends=('python' 'python-yaml' 'python-numpy' 'python-rich' 'python-click')
makedepends=('python-setuptools')
url="https://github.com/mcgillij/amdfan"
source=("file:///home/j/gits/amdfan/dist/${pkgname}-${pkgver}.tar.gz")
#source=("https://github.com/mcgillij/amdfan/archive/${pkgver}.tar.gz")
md5sums=('SKIP')

build() {
  cd "$srcdir/$pkgname-$pkgver"
  sed -i "s/PROJECTVERSION/$pkgver/g" setup.py
  python setup.py build
}

package() {
  cd "$srcdir/$pkgname-$pkgver"
  sed -i "s/PROJECTVERSION/$pkgver/g" setup.py
  python setup.py install --prefix=/usr --root="$pkgdir"
  mkdir -p "$pkgdir/usr/lib/systemd/system"
  install -Dm644 amdfan/amdfan.service "$pkgdir/usr/lib/systemd/system/"
} 
